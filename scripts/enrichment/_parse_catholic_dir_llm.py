"""
Parse Catholic Directory (1907) using DeepSeek LLM.
Splits text into diocese sections, sends each to DeepSeek for structured extraction.
"""
import re, csv, json, os, time, sys
from tqdm import tqdm
import httpx

OUT_DIR = 'data/catholic_directory_1907'
os.makedirs(OUT_DIR, exist_ok=True)

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/v1/chat/completions'
MODEL = 'deepseek-chat'

HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

SYSTEM_PROMPT = """You are parsing a 1907 Catholic Directory. Extract ALL religious institutions from the text.

For each institution, output a JSON object with these fields:
- "name": The institution name (clean, standardized)
- "type": One of: "church", "school", "orphanage", "hospital", "college", "convent", "seminary", "chapel", "cemetery", "mission", "home", "monastery", "industrial_school", "other"
- "parent_name": The name of the governing institution (the parish/church it belongs to, or the diocese name)
- "parent_type": "church" if parent is a parish, "diocese" if directly under diocese
- "city": The city or town
- "address": Street address if present (or empty string)
- "religious_order": Religious order running it, if mentioned (e.g., "Sisters of Charity", "Jesuits")

Rules:
1. EVERY institution gets its own record - churches, schools, orphanages, hospitals, convents, colleges, etc.
2. Schools, orphanages, hospitals and convents listed under a church should have that church as parent_name.
3. Standalone institutions have parent_name = diocese name.
4. Handle OCR noise gracefully - two-column layout artifacts, broken words.
5. Clean up names: "ST. ALPHONSUS' (German)" becomes "St. Alphonsus (German)"
6. Output ONLY a valid JSON array. No markdown, no code fences."""

def extract_json(text):
    """Extract JSON array from response text, handling truncation and code fences."""
    text = re.sub(r'```(?:json)?', '', text).strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Find JSON array (may be truncated without closing ])
    start = text.find('[')
    if start >= 0:
        # Try with progressively shorter content (in case of truncation)
        for end_pos in [len(text), text.rfind('}'), text.rfind('"'), text.rfind(']')]:
            if end_pos < 0:
                continue
            candidate = text[start:end_pos + 1]
            # If it doesn't end with ], add it
            if not candidate.endswith(']'):
                # Find last complete object
                last_obj = candidate.rfind('}')
                if last_obj > 0:
                    candidate = candidate[:last_obj + 1] + '\n]'
            try:
                data = json.loads(candidate)
                if isinstance(data, list):
                    return data
            except:
                continue
    
    # Try single object (for dict responses)
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        return v
                return [data]
        except:
            pass
    
    return None

def parse_section(dio_name, section_text, section_num):
    """Send a diocese section to DeepSeek and parse the response."""
    for marker in ['RECAPITULATION', 'RELIGIOUS COMMUNITIES', 'INSTITUTIONS IN CHARGE']:
        pos = section_text.find(marker)
        if pos > 0:
            section_text = section_text[:pos]
    
    if len(section_text) > 120000:
        section_text = section_text[:120000]
        last_nl = section_text.rfind('\n')
        if last_nl > 80000:
            section_text = section_text[:last_nl]
    
    user_prompt = f"""Extract all institutions from the {dio_name} section of a 1907 Catholic Directory.

Diocese: {dio_name}
Section {section_num} of 32.

Text:
{section_text}"""
    
    payload = {
        'model': MODEL,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': user_prompt}
        ],
        'temperature': 0.01,
        'max_tokens': 8192
    }
    
    print(f'  [{len(section_text):,} chars] ', end='', flush=True)
    for attempt in range(3):
        try:
            r = httpx.post(API_URL, headers=HEADERS, json=payload, timeout=180.0)
            
            if r.status_code == 200:
                content = r.json()['choices'][0]['message']['content']
                data = extract_json(content)
                
                if data is None:
                    print(f'JSON fail: {content[:300]}', flush=True)
                    return []
                
                if not isinstance(data, list):
                    data = [data]
                    
                for rec in data:
                    rec['diocese'] = dio_name
                    rec['section'] = section_num
                
                print(f'{len(data)} records', flush=True)
                return data
            
            elif r.status_code in (429, 503):
                wait = min(30 * (attempt + 1), 60)
                print(f'  Rate limited, waiting {wait}s...', flush=True)
                time.sleep(wait)
            else:
                print(f'  API error {r.status_code}: {r.text[:200]}')
                if attempt < 2:
                    time.sleep(5)
        except httpx.TimeoutException:
            print(f'  Timeout', flush=True)
        except Exception as e:
            print(f'  Error: {e}', flush=True)
            if attempt < 2:
                time.sleep(10)
    
    return []

# ============================================================
print('=== Loading text ===', flush=True)
with open(f'{OUT_DIR}/full_text.txt', encoding='utf-8') as f:
    text = f.read()
print(f'  {len(text):,} chars', flush=True)

text = re.sub(r'-\n([a-z])', r'\1', text)

section_starts = [m.end() for m in re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', text)]
print(f'  {len(section_starts)} sections found', flush=True)

section_dioceses = []
for sec_start in section_starts:
    ctx = text[max(0, sec_start - 3000):sec_start]
    hdrs = re.findall(r'((?:ARCH)?DIOCESE)\s+OF\s+([A-Z][A-Z\s\.\-\']+?)(?:\.|\n)', ctx, re.IGNORECASE)
    if hdrs:
        dtype, dname = hdrs[-1]
        section_dioceses.append(f'{dtype} OF {dname.strip().rstrip(".")}')
    else:
        vicars = re.findall(r'((?:VICARIATE|PREFECTURE)[\- ]+APOSTOLIC\s+OF\s+[A-Z][A-Z\s\.\-]+)', ctx, re.IGNORECASE)
        section_dioceses.append(vicars[-1].strip().upper() if vicars else 'UNKNOWN')

for i, d in enumerate(section_dioceses):
    print(f'  Section {i+1:2d}: {d}', flush=True)

# ============================================================
print(f'\n=== Parsing with {MODEL} (32 sections) ===', flush=True)

all_records = []
error_sections = []

for i in tqdm(range(len(section_starts)), desc='LLM parsing'):
    sec_start = section_starts[i]
    sec_end = section_starts[i + 1] if i + 1 < len(section_starts) else len(text)
    
    section_text = text[sec_start:sec_end]
    dio_name = section_dioceses[i]
    
    records = parse_section(dio_name, section_text, i + 1)
    all_records.extend(records)
    
    if not records:
        error_sections.append((i + 1, dio_name))
    
    if i < len(section_starts) - 1:
        time.sleep(0.5)

# ============================================================
print(f'\n=== Results ===', flush=True)
print(f'Total records: {len(all_records):,}', flush=True)

if error_sections:
    print(f'\nFailed sections ({len(error_sections)}):', flush=True)
    for num, name in error_sections:
        print(f'  Section {num}: {name}', flush=True)

print('\n=== By type ===', flush=True)
type_counts = {}
for r in all_records:
    t = r.get('type', 'unknown')
    type_counts[t] = type_counts.get(t, 0) + 1
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c:,}', flush=True)

print('\n=== By diocese (top 15) ===', flush=True)
dio_counts = {}
for r in all_records:
    d = r.get('diocese', 'UNKNOWN')
    dio_counts[d] = dio_counts.get(d, 0) + 1
for d, c in sorted(dio_counts.items(), key=lambda x: -x[1])[:15]:
    print(f'  {d}: {c:,}', flush=True)

# Save
print('\n=== Saving ===', flush=True)
csv_path = f'{OUT_DIR}/institutions_llm.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    fields = ['diocese', 'section', 'name', 'type', 'parent_name', 'parent_type', 
              'city', 'address', 'religious_order']
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    for r in all_records:
        w.writerow(r)
print(f'CSV: {csv_path} ({len(all_records):,} rows)', flush=True)

json_path = f'{OUT_DIR}/institutions_llm.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2, ensure_ascii=False)
print(f'JSON: {json_path}', flush=True)

print('\nDone!', flush=True)

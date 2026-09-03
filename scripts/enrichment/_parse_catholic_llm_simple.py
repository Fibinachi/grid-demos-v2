"""Simple LLM-based Catholic Directory parser."""
import re, json, csv, os, time, sys, requests

API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
OUT = 'data/catholic_directory_1907'
os.makedirs(OUT, exist_ok=True)

print('Loading...')
ct = open(f'{OUT}/full_text.txt', encoding='utf-8').read()
ct = re.sub(r'-\n([a-z])', r'\1', ct)

sections = [m.end() for m in re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', ct)]
print(f'{len(sections)} sections')

# Get diocese names
dioceses = []
for ss in sections:
    ctx = ct[max(0, ss-3000):ss]
    h = re.findall(r'((?:ARCH)?DIOCESE)\s+OF\s+([A-Z][A-Z\s.\-\']+?)(?:\.|\n)', ctx, re.IGNORECASE)
    if h:
        dtype, dname = h[-1]
        dioceses.append(f'{dtype.upper()} OF {dname.strip().rstrip(".")}')
    else:
        dioceses.append('UNKNOWN')

for i, d in enumerate(dioceses):
    print(f'  {i+1}: {d}')

system_prompt = """Extract ALL religious institutions from this 1907 Catholic Directory text as a JSON array.
Each object has: name, type (church/school/orphanage/hospital/college/convent/seminary/chapel/home/other), parent_name, parent_type (church/diocese), city, address, religious_order.
Schools/orphanages/hospitals under a church have that church as parent_name.
Output ONLY raw JSON with no markdown, no code fences."""

all_records = []

for i in range(len(sections)):
    start = sections[i]
    end = sections[i+1] if i+1 < len(sections) else len(ct)
    text = ct[start:end]
    
    for marker in ['RECAPITULATION', 'RELIGIOUS COMMUNITIES', 'INSTITUTIONS IN CHARGE']:
        p = text.find(marker)
        if p > 0:
            text = text[:p]
    
    dio = dioceses[i]
    sys.stdout.write(f'{i+1}/{len(sections)} {dio} ({len(text):,}c)... ')
    sys.stdout.flush()
    
    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Text:\n{text}'}
        ],
        'temperature': 0.01,
        'max_tokens': 8192
    }
    
    try:
        r = requests.post('https://api.deepseek.com/v1/chat/completions', headers=HEADERS, json=payload, timeout=300)
        if r.status_code != 200:
            print(f'HTTP {r.status_code}')
            continue
        
        content = r.json()['choices'][0]['message']['content']
        content = re.sub(r'```(?:json)?', '', content).strip()
        
        # Parse JSON - handle truncation by closing incomplete array
        data = None
        try:
            data = json.loads(content)
        except:
            # Try truncated fix: close the array at last complete object
            if content.startswith('['):
                last_obj = content.rfind('}')
                if last_obj > 0:
                    try:
                        data = json.loads(content[:last_obj+1] + ']')
                    except:
                        pass
        
        if not data:
            print(f'PARSE FAIL')
            continue
        
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    data = v
                    break
            else:
                data = [data]
        elif not isinstance(data, list):
            data = [data]
        
        for rec in data:
            rec['diocese'] = dio
            rec['section'] = i+1
        
        all_records.extend(data)
        print(f'{len(data)} records')
    
    except Exception as e:
        print(f'ERROR: {e}')
    
    if i < len(sections) - 1:
        time.sleep(0.3)

# Results
print(f'\nTotal: {len(all_records):,} records')

types = {}
for r in all_records:
    t = r.get('type', '?')
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c}')

# Save
csv_path = f'{OUT}/institutions_llm.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['diocese','section','name','type','parent_name','parent_type','city','address','religious_order'], extrasaction='ignore')
    w.writeheader()
    for r in all_records:
        w.writerow(r)
print(f'Saved: {csv_path}')

json_path = f'{OUT}/institutions_llm.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2, ensure_ascii=False)
print(f'Saved: {json_path}')
print('Done!')

"""
parse_catholic_directory_1865.py — Full extraction of the 1865 Catholic Almanac.
Uses "CHURCHES AND CLERGY" markers as anchors, identifies diocese from context.

Strategy:
1. Find all "CHURCHES AND CLERGY" markers
2. For each, look backwards to identify the diocese
3. Extract chunk from CC marker to next CC marker
4. Send each chunk to DeepSeek for structured extraction
5. Save all results as JSON for Phase 2 matching
"""
import json, os, re, sys, time, requests
from datetime import datetime, timezone

DATA_DIR = 'E:/grid/data/directories'
OUTPUT_FILE = os.path.join(DATA_DIR, 'parishes_1865.json')
PROGRESS_FILE = os.path.join(DATA_DIR, 'parishes_1865_progress.json')
OCR_PATH = os.path.join(DATA_DIR, 'catholic_dir_1865.txt')

# Diocese -> state mapping
DIOCESE_STATE = {
    'BALTIMORE': 'MD', 'PITTSBURGH': 'PA', 'CHARLESTON': 'SC',
    'ERIE': 'PA', 'PHILADELPHIA': 'PA', 'RICHMOND': 'VA',
    'SAVANNAH': 'GA', 'WHEELING': 'WV',
    'NEW-YORK': 'NY', 'NEW YORK': 'NY', 'NEW_YORK': 'NY',
    'ALBANY': 'NY', 'BOSTON': 'MA', 'BROOKLYN': 'NY',
    'BURLINGTON': 'VT', 'HARTFORD': 'CT', 'PORTLAND': 'ME',
    'NEWARK': 'NJ', 'BUFFALO': 'NY',
    'CLEVELAND': 'OH', 'COVINGTON': 'KY', 'DETROIT': 'MI',
    'LOUISVILLE': 'KY', 'VINCENNES': 'IN', 'FORT WAYNE': 'IN',
    'CHICAGO': 'IL', 'DUBUQUE': 'IA', 'NASHVILLE': 'TN',
    'SANTA FE': 'NM', 'SANTA_FE': 'NM', 'SANTA FR': 'NM',
    'ST. PAUL': 'MN', 'ST PAUL': 'MN',
    'ST. LOUIS': 'MO', 'ST LOUIS': 'MO', 'ALTON': 'IL',
    'MONTEREY AND LOS ANGELES': 'CA',
    'SAN FRANCISCO': 'CA', 'OREGON CITY': 'OR', 'OREGON, CITY': 'OR',
    'NESQUALY': 'WA', 'NEW-ORLEANS': 'LA', 'NEW ORLEANS': 'LA',
    'GALVESTON': 'TX', 'LITTLE ROCK': 'AR', 'MOBILE': 'AL',
    'NATCHEZ': 'MS', 'NATCHITOCHES': 'LA',
    'SAULT-SAINTE-MARIE': 'MI', 'SAUT-SAINTE-MARIE': 'MI',
    'MILWAUKEE': 'WI', 'CINCINNATI': 'OH',
    # Canada
    'QUEBEC': 'QC', 'THREE RIVERS': 'QC', 'MONTREAL': 'QC',
    'ST. HYACINTH': 'QC', 'ST HYACINTH': 'QC',
    'OTTAWA': 'ON', 'OTTAWA, U': 'ON', 'OTTAWA, U. C': 'ON',
    'KINGSTON': 'ON', 'TORONTO': 'ON',
    'SANDWICH': 'ON', 'SANDWICH, C': 'ON', 'SANDWICH, C. W': 'ON',
    'HAMILTON': 'ON',
    'ST. BONIFACE': 'MB', 'ARICHAT': 'NS', 'HALIFAX': 'NS',
    'ST. JOHN': 'NB', 'ST JOHN': 'NB', 'ST. JOHN, N': 'NB', 'ST JOHN, N': 'NB',
    'CHARLOTTETOWN': 'PE',
    'CHATHAM': 'NB', 'CHATHAM, N': 'NB',
    'ST. JOHNS': 'NL', 'ST JOHNS': 'NL', 'ST. JOHNS, N': 'NL',
    'HARBOR GRACE': 'NL',
}

SYSTEM_PROMPT = """You are extracting structured parish data from OCR text of the 1865 Catholic Almanac (Sadlier's Catholic Directory).

The OCR is VERY noisy (1865 typeface + Tesseract errors). You MUST correct obvious OCR errors.

Extract EVERY religious institution — parishes, missions, schools, orphanages, hospitals, convents, seminaries, cemeteries, asylums. ALL are religious infrastructure.

For EACH, return:
{
  "name": "Full corrected name",
  "city": "City/town name (correct OCR errors!)",
  "county": "County if mentioned",
  "institution_type": "parish|mission|school|orphanage|hospital|convent|seminary|cemetery|asylum|college|chapel|other",
  "clergy": [{"name": "Full corrected name", "title": "PASTOR|ASSISTANT|RECTOR|VICAR_GENERAL|ARCHBISHOP|BISHOP|CHAPLAIN|SUPERIOR"}],
  "notes": "Language (German/French/etc.), religious order (SJ/OSB/OSF/etc.), gender served (boys/girls/men/women)",
  "is_mission": true/false
}

CRITICAL RULES:
1. **OCR CORRECTION - NAMES**: Fix: "Jno."->"John", "Thos."->"Thomas", "Jas."->"James", "Geo."->"George", "Wm."->"William", "Chas."->"Charles", "Robt."->"Robert", "Edw."->"Edward", "Ricd."->"Richard", "Michl."->"Michael", "Patk."->"Patrick", "Anth."->"Anthony", "Bern."->"Bernard", "Jos."->"Joseph", "Matt."->"Matthew"

2. **OCR CORRECTION - CITIES**: Fix garbled city names using context. Use county names as hints.

3. **INSTITUTION TYPE**: Classify each entry:
   - parish: church with resident pastor and congregation
   - mission: "attended from", "visited from", "station" — no resident priest
   - school: "School", "Academy", "College", "University", "Institute"
   - orphanage: "Orphan Asylum", "Orphanage", "Foundling"
   - hospital: "Hospital", "Infirmary", "Sanitarium"
   - convent: "Convent", "Monastery", "Sisters of...", "Motherhouse"
   - seminary: "Seminary", "Ecclesiastical"
   - cemetery: "Cemetery", "Calvary", "Burial ground"
   - asylum: "Asylum" (non-orphan), "Reform School", "Industrial School"
   - chapel: institutional chapel (not a parish)
   - college: degree-granting institution
   - other: anything else religious

4. **CLERGY**: Extract ALL named personnel.
   - At parishes: first "Rev." = PASTOR, subsequent = ASSISTANT
   - At institutions: "Rev." = CHAPLAIN, "Sister"/"Mother" = SUPERIOR
   - "Very Rev." = VICAR_GENERAL or RECTOR
   - "Most Rev." = ARCHBISHOP, "Rt. Rev." = BISHOP

5. **MISSIONS**: "attended from X" or "visited from" -> is_mission=true, institution_type="mission"

6. **SKIP ONLY**: Advertisements, religious goods sellers, page headers, summary tables. Extract EVERYTHING else.

Return ONLY a JSON array. No markdown, no explanation, no code fences."""


def load_text():
    return open(OCR_PATH, 'r', encoding='utf-8', errors='ignore').read()


def find_parish_sections(text):
    """Find parish listing sections using CHURCHES AND CLERGY markers."""
    cc_markers = list(re.finditer(r'CHURCH(?:ES)?\s+AND\s+CLERGY', text, re.IGNORECASE))
    print(f"  Found {len(cc_markers)} CC markers")
    
    sections = []
    seen_keys = set()
    
    for i, cc in enumerate(cc_markers):
        pos = cc.start()
        
        # Look backwards up to 6000 chars for a DIOCESE OF header
        back_start = max(0, pos - 6000)
        back_text = text[back_start:pos]
        
        diocese_matches = list(re.finditer(
            r'DIOCESE\s+OF\s+([A-Z][A-Z\s\-.,/]{2,60}?)(?:\.(?:\s|\n)|[\s\n]{2,})',
            back_text, re.IGNORECASE
        ))
        
        diocese_name = None
        state = None
        if diocese_matches:
            raw = diocese_matches[-1].group(1).strip().rstrip('.,').strip()
            diocese_name = re.sub(r'\s+', ' ', raw).upper().strip()
            diocese_name = re.sub(r'[,\-]\s*$', '', diocese_name)
        
        if diocese_name:
            for key, st in DIOCESE_STATE.items():
                if key.upper() == diocese_name.upper():
                    state = st
                    break
        
        # Chunk size: 6000 chars (well within API limits, 6000 token output is enough)
        CHUNK_SIZE = 4000  # Smaller = faster API calls, fewer rate limits
        end = pos + 25000
        if i + 1 < len(cc_markers):
            end = min(end, cc_markers[i + 1].start())
        end = min(end, len(text))
        
        full_chunk = text[pos:end]
        
        # Deduplicate: skip same diocese
        section_key = f"{diocese_name}_{state}"
        if section_key in seen_keys:
            continue
        seen_keys.add(section_key)
        
        # Split large sections into manageable chunks
        if len(full_chunk) <= CHUNK_SIZE:
            sections.append({
                'diocese': diocese_name or 'UNKNOWN',
                'state': state,
                'position': pos,
                'chunk': full_chunk,
                'chunk_size': len(full_chunk),
            })
        else:
            for chunk_start in range(0, len(full_chunk), CHUNK_SIZE - 500):
                chunk_end = min(chunk_start + CHUNK_SIZE, len(full_chunk))
                sub_chunk = full_chunk[chunk_start:chunk_end]
                if len(sub_chunk) > 500:
                    sections.append({
                        'diocese': f"{diocese_name or 'UNKNOWN'}_pt{chunk_start//CHUNK_SIZE}",
                        'state': state,
                        'position': pos + chunk_start,
                        'chunk': sub_chunk,
                        'chunk_size': len(sub_chunk),
                    })
    
    return sections


def call_deepseek(chunk, diocese_name, year=1865):
    """Send diocese chunk to DeepSeek, return parsed JSON."""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        return None, "No API key"
    
    user_prompt = f"Extract all parishes, missions, and stations from this {year} Catholic Directory section for the Diocese of {diocese_name}:\n\n{chunk}"
    
    for attempt in range(3):
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": 0.05,
                    "max_tokens": 6000,
                },
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                timeout=120)
            
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                cleaned = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
                cleaned = re.sub(r'\n?```\s*$', '', cleaned)
                start = cleaned.find('[')
                if start == -1:
                    return None, f"No JSON array in response"
                depth = 0
                for j in range(start, len(cleaned)):
                    if cleaned[j] == '[':
                        depth += 1
                    elif cleaned[j] == ']':
                        depth -= 1
                        if depth == 0:
                            return json.loads(cleaned[start:j+1]), None
            
            elif resp.status_code == 429:
                wait = 10 * (attempt + 1)  # 10s, 20s, 30s
                print(f"\n     Rate limited, waiting {wait}s...", end="", flush=True)
                time.sleep(wait)
                continue
            elif resp.status_code == 400:
                # Likely too long - return error so caller can split
                err_msg = resp.json().get('error', {}).get('message', str(resp.text[:200]))
                return None, f"HTTP 400: {err_msg[:120]}"
            else:
                return None, f"HTTP {resp.status_code}: {resp.text[:150]}"
        
        except json.JSONDecodeError as e:
            return None, f"JSON error: {str(e)[:80]}"
        except Exception as e:
            return None, f"Error: {str(e)[:80]}"
    
    return None, "Max retries"


def save_progress(results):
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


def main():
    year = 1865
    print("=" * 70)
    print(f"{year} CATHOLIC ALMANAC - FULL DIRECTORY PARSE")
    print("=" * 70)
    
    if not os.environ.get("DEEPSEEK_API_KEY"):
        print("\nSet DEEPSEEK_API_KEY environment variable first!")
        sys.exit(1)
    
    print("\nLoading OCR text...")
    text = load_text()
    print(f"  {len(text):,} chars")
    
    print("\nFinding parish sections...")
    sections = find_parish_sections(text)
    print(f"  {len(sections)} unique sections\n")
    
    # Load previous progress
    all_results = {}
    if os.path.exists(PROGRESS_FILE):
        all_results = json.load(open(PROGRESS_FILE, 'r', encoding='utf-8'))
        print(f"Resuming: {len(all_results)} dioceses already parsed\n")
    
    total_parishes = 0
    total_missions = 0
    total_clergy = 0
    
    for i, section in enumerate(sections):
        diocese = section['diocese']
        state = section['state'] or '??'
        key = f"{diocese}_{state}"
        
        if key in all_results:
            existing = len(all_results[key])
            total_parishes += sum(1 for p in all_results[key] if not p.get('is_mission', False))
            total_missions += sum(1 for p in all_results[key] if p.get('is_mission', False))
            total_clergy += sum(len(p.get('clergy', [])) for p in all_results[key])
            print(f"  SKIP [{i+1:2d}/{len(sections)}] {diocese:35s} {state:4s} - already parsed ({existing} entries)")
            continue
        
        print(f"  [{i+1:2d}/{len(sections)}] {diocese:35s} {state:4s} ({section['chunk_size']:,} chars)", end="", flush=True)
        
        parishes, error = call_deepseek(section['chunk'], diocese, year)
        
        if parishes and isinstance(parishes, list):
            all_results[key] = parishes
            n_parishes = sum(1 for p in parishes if not p.get('is_mission', False))
            n_missions = sum(1 for p in parishes if p.get('is_mission', False))
            n_clergy = sum(len(p.get('clergy', [])) for p in parishes)
            total_parishes += n_parishes
            total_missions += n_missions
            total_clergy += n_clergy
            
            print(f" -> {len(parishes)} entries ({n_parishes}p, {n_missions}m, {n_clergy}c)")
            
            for p in parishes[:2]:
                clergy_str = ', '.join(
                    f"{c.get('name','?')} ({c.get('title','?')})" 
                    for c in p.get('clergy', [])[:2]
                )
                city = p.get('city') or '?'
                name = p.get('name') or '?'
                miss = ' [M]' if p.get('is_mission') else ''
                print(f"       {name[:55]:55s} | {city[:25]:25s} | {clergy_str}{miss}")
        else:
            print(f" -> FAIL: {error}")
        
        save_progress(all_results)
        
        if i < len(sections) - 1:
            time.sleep(2)  # Rate limit protection between chunks
    
    # Final save
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 70}")
    print(f"DONE")
    print(f"  Dioceses:        {len(all_results)}")
    print(f"  Parishes:        {total_parishes:,}")
    print(f"  Missions:        {total_missions:,}")
    print(f"  Total entries:   {total_parishes + total_missions:,}")
    print(f"  Clergy records:  {total_clergy:,}")
    print(f"  Output:          {OUTPUT_FILE}")
    print(f"  Progress:        {PROGRESS_FILE}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()

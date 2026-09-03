"""
Ireland Register of Charities — Classify & Import Religious Orgs
=================================================================
1. Scans the Charity Classification column for religious categories
2. For unclassified-but-religious names, uses DeepSeek AI
3. Imports confirmed religious charities as new church records
"""
import openpyxl, csv, json, os, sys, re, time, urllib.request, urllib.parse
from datetime import datetime

sys.path.insert(0, r'E:\grid')
from gw_db import connect, log_change

XLSX_PATH = r'E:\grid\data\ireland_charities_register.xlsx'
SOURCE = 'ireland_charities_register'
DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'
CHECKPOINT = r'E:\grid\data\ireland_religious_classified.json'

# Religious classification keywords for pre-filter
RELIGIOUS_KEYWORDS = [
    'CHURCH', 'CHAPEL', 'CATHEDRAL', 'MINISTRY', 'MINISTRIES',
    'CATHOLIC', 'ROMAN CATH', 'PARISH', 'DIOCESE', 'ARCHDIOCESE',
    'PRESBYTERIAN', 'METHODIST', 'BAPTIST', 'LUTHERAN', 'EPISCOPAL',
    'QUAKER', 'MORAVIAN', 'MENNONITE',
    'PENTECOSTAL', 'EVANGELICAL', 'GOSPEL', 'APOSTOLIC',
    'ORTHODOX', 'COPTIC', 'MARONITE',
    'SALVATION ARMY', 'JEHOVAH', 'MORMON', 'LDS',
    'MOSQUE', 'ISLAMIC', 'MASJID', 'MUSLIM', 'AHMADIYYA',
    'SYNAGOGUE', 'JEWISH', 'RABBI', 'SHALOM', 'YESHIVA',
    'HINDU', 'MANDIR', 'TEMPLE', 'BUDDHIST', 'VIHARA', 'SIKH',
    'GURDWARA', 'JAIN',
    'MONASTERY', 'CONVENT', 'PRIORY', 'ABBEY', 'FRIARY',
    'CHRISTIAN', 'CROSS', 'CALVARY', 'BIBLE', 'PRAYER',
    'FAITH', 'GRACE', 'TRINITY', 'HOLY', 'SAINT', 'ST ',
    'MISSION', 'MISSIONARY',
    'CARMELITE', 'DOMINICAN', 'FRANCISCAN', 'JESUIT', 'AUGUSTINIAN',
    'BENEDICTINE', 'SALESIAN', 'REDEMPTORIST', 'VINCENT DE PAUL',
    'CLERGY', 'CHAPLAIN', 'PASTORAL', 'ECUMENICAL',
    'WORSHIP', 'FELLOWSHIP', 'CONGREGATION',
]

# Keywords that suggest NON-religious despite religious-sounding name
NON_RELIGIOUS_KEYWORDS = [
    'SCOUT', 'GUIDE', 'SCOUTING', 'YOUTH CLUB',
    'FOOTBALL', 'GAA', 'SPORTS', 'ATHLETIC',
    'SCHOOL', 'COLLEGE', 'UNIVERSITY', 'EDUCATION',
    'HOSPITAL', 'CLINIC', 'MEDICAL',
    'MUSEUM', 'GALLERY', 'THEATRE', 'THEATER',
    'HISTORICAL', 'HERITAGE',
    'COMMUNITY CENTRE', 'COMMUNITY CENTER',
    'SOCIAL CLUB', 'MEN\'S SHED', 'WOMEN\'S SHED',
]


def is_likely_religious(name):
    """Quick keyword pre-filter."""
    n = (name or '').upper()
    # First check non-religious patterns
    for kw in NON_RELIGIOUS_KEYWORDS:
        if kw in n:
            return False
    # Then check religious patterns
    for kw in RELIGIOUS_KEYWORDS:
        if kw in n:
            return True
    return False


CLASSIFICATION_PROMPT = """You are classifying Irish charity names. Determine if each is a religious organization.

A religious organization is one primarily focused on:
- Religious worship, services, or ceremonies (church, mosque, synagogue, temple)
- Spreading or teaching religious faith (missionary, evangelical, pastoral)
- Running a religious order or community (monastery, convent, abbey)
- Religious education (seminary, bible college)
- Religious charitable work under a religious identity (St Vincent de Paul, Catholic housing association)

NOT religious (even if name sounds religious):
- Scout troops, guide groups, youth clubs (even if called "St Patrick's Scouts")
- Sports clubs, GAA clubs (even if religious-sounding name)
- Schools, colleges, universities (educational, not religious)
- Hospitals, medical centers (healthcare, not religious)
- Museums, historical societies
- Community centers, social clubs
- Generic "St." or "Saint" names that are schools, scouts, sports

For each name, respond with:
faith: "christian", "muslim", "jewish", "hindu", "buddhist", "sikh", "other_religious", or "non_religious"
denomination: specific denomination if christian (e.g., "Catholic", "Presbyterian", "Church of Ireland", "Methodist", "Baptist", "Pentecostal", "Orthodox", "Evangelical", "Quaker", "Salvation Army", "Jehovah's Witnesses", "Mormon", "Interdenominational", etc.) or null
landmark_type: "church", "mosque", "synagogue", "temple", "monastery", "convent", "mission", "religious_order", "charitable_org", or "other"
confidence: 0.0-1.0

RESPOND ONLY with a JSON array: [{"name":"...","faith":"...","denomination":null|"...","landmark_type":"...","confidence":0.0}]"""


def call_deepseek(batch):
    """Send batch to DeepSeek for classification."""
    names_text = '\n'.join(f"{i+1}. {n}" for i, n in enumerate(batch))
    
    payload = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': CLASSIFICATION_PROMPT},
            {'role': 'user', 'content': f'Classify these Irish charity names:\n{names_text}'}
        ],
        'temperature': 0.1,
        'max_tokens': 3000,
    }).encode()
    
    req = urllib.request.Request(DEEPSEEK_URL, data=payload, headers={
        'Authorization': f'Bearer {DEEPSEEK_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': 'GrantWizard/1.0',
    })
    
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            result = json.loads(resp.read())
        content = result['choices'][0]['message']['content']
        start = content.find('[')
        end = content.rfind(']') + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return None
    except Exception as e:
        print(f'    API error: {e}')
        return None


def main():
    print("=" * 70)
    print("Ireland Register of Charities — Religious Classification & Import")
    print("=" * 70)
    
    if not DEEPSEEK_KEY:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return
    
    # Step 1: Load XLSX and pre-filter (single pass)
    print("\n[1/4] Loading XLSX and pre-filtering religious charities...")
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb['Public Register']
    
    headers = [str(h).strip() if h else '' for h in next(ws.iter_rows(min_row=2, max_row=2, values_only=True))]
    print(f"  Headers: {[h for h in headers if h]}")
    
    candidates = []
    total = 0
    
    for row in ws.iter_rows(min_row=3, values_only=True):
        total += 1
        name = str(row[1] or '')
        
        if is_likely_religious(name):
            candidates.append({
                'number': str(row[0] or ''),
                'name': name,
                'aka': str(row[2] or ''),
                'status': str(row[3] or ''),
                'classification': str(row[4] or ''),
                'address': str(row[5] or ''),
                'purpose': str(row[10] or '')[:200],
            })
        else:
            # Check classification/purpose for religious themes
            classification = str(row[4] or '')
            purpose = str(row[10] or '')
            combined = (classification + ' ' + purpose).upper()
            if any(w in combined for w in ['RELIGIOUS', 'ECCLESIASTICAL',
                                            'CLERGY', 'CHAPLAIN', 'WORSHIP']):
                candidates.append({
                    'number': str(row[0] or ''),
                    'name': name,
                    'aka': str(row[2] or ''),
                    'status': str(row[3] or ''),
                    'classification': classification,
                    'address': str(row[5] or ''),
                    'purpose': purpose[:200],
                })
    
    wb.close()
    print(f"  Total rows scanned: {total:,}")
    print(f"  Candidates found: {len(candidates):,}")
    
    # Step 2: Deduplicate by charity number
    seen = set()
    unique_candidates = []
    for c in candidates:
        if c['number'] not in seen:
            seen.add(c['number'])
            unique_candidates.append(c)
    print(f"  Unique candidates: {len(unique_candidates):,}")
    
    # Step 3: Classify with DeepSeek in batches
    print("\n[2/4] Classifying candidates with DeepSeek AI...")
    
    classified = []
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            classified = json.load(f)
        print(f"  Loaded {len(classified)} from checkpoint")
        classified_names = {c.get('name') for c in classified}
        unique_candidates = [c for c in unique_candidates if c['name'] not in classified_names]
        print(f"  Remaining to classify: {len(unique_candidates)}")
    
    BATCH_SIZE = 20
    results = list(classified)
    api_calls = 0
    errors = 0
    
    for i in range(0, len(unique_candidates), BATCH_SIZE):
        batch = unique_candidates[i:i + BATCH_SIZE]
        names = [c['name'] for c in batch]
        
        print(f"  Batch {i//BATCH_SIZE + 1}/{(len(unique_candidates) + BATCH_SIZE - 1)//BATCH_SIZE}...", end='')
        
        result = call_deepseek(names)
        
        if result:
            # Merge DeepSeek results back with candidate data
            for r in result:
                r_name = r.get('name', '').strip().upper()
                # Find matching candidate
                for c in batch:
                    if c['name'].strip().upper() == r_name:
                        r.update(c)
                        break
                results.append(r)
            api_calls += 1
            print(f" ✅ {len(result)} classified")
        else:
            errors += 1
            print(f" ❌")
        
        # Save checkpoint
        if api_calls % 10 == 0 or errors >= 3:
            with open(CHECKPOINT, 'w') as f:
                json.dump(results, f, indent=2)
        
        if errors >= 5:
            print("  Too many errors, stopping")
            break
        
        time.sleep(0.3)
    
    # Save final checkpoint
    with open(CHECKPOINT, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  Total classified: {len(results)}")
    print(f"  API calls: {api_calls}, Errors: {errors}")
    
    # Step 4: Filter to religious only and import
    print("\n[3/4] Filtering religious organizations...")
    
    religious = [r for r in results 
                 if r.get('faith') and r['faith'] != 'non_religious' 
                 and r.get('confidence', 0) >= 0.5]
    
    non_religious = [r for r in results 
                     if r.get('faith') == 'non_religious' 
                     or r.get('confidence', 0) < 0.5]
    
    print(f"  Religious: {len(religious)}")
    print(f"  Non-religious: {len(non_religious)}")
    
    # Faith breakdown
    faith_counts = {}
    for r in religious:
        f = r.get('faith', 'unknown')
        faith_counts[f] = faith_counts.get(f, 0) + 1
    for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
        print(f"    {f}: {c}")
    
    # Step 5: Import to DB
    print("\n[4/4] Importing to churches.db...")
    conn = connect(r'E:\grid\churches.db')
    
    # Check existing Irish records to avoid dupes
    existing_irish = set()
    for row in conn.execute("SELECT cra_bn FROM churches WHERE country='Ireland' AND cra_bn IS NOT NULL").fetchall():
        if row[0]:
            existing_irish.add(row[0])
    
    # Also check for Ireland charities by source
    existing_source = set()
    for row in conn.execute("SELECT cra_bn FROM churches WHERE source=? AND cra_bn IS NOT NULL", (SOURCE,)).fetchall():
        if row[0]:
            existing_source.add(row[0])
    
    print(f"  Existing Irish church records: {len(existing_irish)}")
    print(f"  Already imported from this source: {len(existing_source)}")
    
    imported = 0
    skipped_existing = 0
    skipped_non = 0
    
    faith_map = {
        'christian': 'Christian', 'muslim': 'Islam', 'jewish': 'Judaism',
        'hindu': 'Hindu', 'buddhist': 'Buddhist', 'sikh': 'Sikh',
        'other_religious': 'Other',
    }
    
    for r in religious:
        charity_num = r.get('number', '')
        if charity_num in existing_irish or charity_num in existing_source:
            skipped_existing += 1
            continue
        
        faith = faith_map.get(r.get('faith', ''), 'Other')
        denom = r.get('denomination')
        lm_type = r.get('landmark_type', 'church')
        name = r.get('name', '')[:200]
        address = r.get('address', '')[:200]
        purpose = r.get('purpose', '')[:500]
        
        # Parse Irish address for city
        city = None
        if address:
            # Irish addresses often have format: ..., TOWN, COUNTY
            parts = [p.strip() for p in address.split(',')]
            if len(parts) >= 2:
                city = parts[-2] if len(parts) >= 2 else parts[0]
        
        try:
            conn.execute("""
                INSERT INTO churches (
                    name, faith, denomination, city, country,
                    address, landmark_type, source,
                    cra_bn, charitable_purpose,
                    last_updated
                ) VALUES (?, ?, ?, ?, 'Ireland', ?, ?, ?, ?, ?, date('now'))
            """, (
                name, faith, denom, city, address,
                lm_type, SOURCE,
                charity_num, purpose,
            ))
            
            imported += 1
            if imported % 100 == 0:
                conn.commit()
                print(f"    Imported {imported}...")
                
        except Exception as e:
            print(f"    ERROR: {e}")
            skipped_non += 1
    
    conn.commit()
    
    print(f"\n{'='*70}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*70}")
    print(f"  Candidates classified: {len(results):,}")
    print(f"  Religious identified:  {len(religious):,}")
    print(f"  Imported to DB:        {imported}")
    print(f"  Skipped (existing):    {skipped_existing}")
    print(f"  Skipped (errors):      {skipped_non}")
    
    # Show sample imports
    if imported > 0:
        print(f"\n  Sample imported:")
        samples = conn.execute(
            "SELECT name, faith, denomination, city FROM churches WHERE source=? AND cra_bn IS NOT NULL LIMIT 10",
            (SOURCE,)
        ).fetchall()
        for s in samples:
            print(f"    {s[0][:50]:50s} | {s[1]:12s} | {s[2] or '-':20s} | {s[3] or '-'}")
    
    conn.close()


if __name__ == '__main__':
    main()

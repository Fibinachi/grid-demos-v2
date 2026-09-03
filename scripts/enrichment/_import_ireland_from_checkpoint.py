"""Import Ireland religious charities from checkpoint + classify remaining."""
import json, os, sys, time, urllib.request
sys.path.insert(0, r'E:\grid')
from gw_db import connect

CHECKPOINT = r'E:\grid\data\ireland_religious_classified.json'
XLSX_PATH = r'E:\grid\data\ireland_charities_register.xlsx'
SOURCE = 'ireland_charities_register'
DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'

CLASSIFICATION_PROMPT = """You are classifying Irish charity names. Determine if each is a religious organization.
faith: "christian", "muslim", "jewish", "hindu", "buddhist", "sikh", "other_religious", or "non_religious"
denomination: specific denomination or null
landmark_type: "church", "mosque", "synagogue", "temple", "monastery", "convent", "mission", "religious_order", "charitable_org", or "other"
confidence: 0.0-1.0
RESPOND ONLY with a JSON array: [{"name":"...","faith":"...","denomination":null|"...","landmark_type":"...","confidence":0.0}]"""

def call_deepseek(batch):
    names_text = '\n'.join(f"{i+1}. {n}" for i, n in enumerate(batch))
    payload = json.dumps({'model': 'deepseek-chat', 'messages': [
        {'role': 'system', 'content': CLASSIFICATION_PROMPT},
        {'role': 'user', 'content': f'Classify these Irish charity names:\n{names_text}'}
    ], 'temperature': 0.1, 'max_tokens': 3000}).encode()
    req = urllib.request.Request(DEEPSEEK_URL, data=payload, headers={
        'Authorization': f'Bearer {DEEPSEEK_KEY}',
        'Content-Type': 'application/json', 'User-Agent': 'GrantWizard/1.0',
    })
    with urllib.request.urlopen(req, timeout=90) as resp:
        result = json.loads(resp.read())
    content = result['choices'][0]['message']['content']
    start = content.find('[')
    end = content.rfind(']') + 1
    return json.loads(content[start:end]) if start >= 0 and end > start else None

# Load checkpoint
classified = json.load(open(CHECKPOINT))
print(f"Checkpoint has {len(classified)} entries")

# Classify remaining 125
classified_names = {c.get('name') for c in classified if c.get('name')}

import openpyxl
wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
ws = wb['Public Register']

remaining = []
for row in ws.iter_rows(min_row=3, values_only=True):
    name = str(row[1] or '')
    if not name:
        continue
    if name not in classified_names:
        remaining.append({
            'number': str(row[0] or ''),
            'name': name,
            'address': str(row[5] or ''),
            'purpose': str(row[10] or '')[:200],
        })

wb.close()
print(f"Remaining to classify: {len(remaining)}")

# Classify in batches
for i in range(0, len(remaining), 20):
    batch = remaining[i:i+20]
    names = [c['name'] for c in batch]
    print(f"  Batch {i//20+1}/{(len(remaining)+19)//20}...", end='')
    
    result = call_deepseek(names)
    if result:
        for r in result:
            r_name = r.get('name', '').strip().upper()
            for c in batch:
                if c['name'].strip().upper() == r_name:
                    r.update(c)
                    break
            classified.append(r)
        print(f" ✅ {len(result)}")
    else:
        print(f" ❌")
    
    time.sleep(0.3)

# Save updated checkpoint
with open(CHECKPOINT, 'w') as f:
    json.dump(classified, f, indent=2)
print(f"\nTotal classified: {len(classified)}")

# Filter religious
religious = [r for r in classified 
             if r.get('faith') and r['faith'] != 'non_religious' 
             and r.get('confidence', 0) >= 0.5]

faith_map = {
    'christian': 'Christian', 'muslim': 'Islam', 'jewish': 'Judaism',
    'hindu': 'Hindu', 'buddhist': 'Buddhist', 'sikh': 'Sikh',
    'other_religious': 'Other',
}

faith_counts = {}
for r in religious:
    f = faith_map.get(r.get('faith', ''), 'Other')
    faith_counts[f] = faith_counts.get(f, 0) + 1

print(f"\nReligious: {len(religious)}")
for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
    print(f"  {f}: {c}")

# Import to DB
conn = connect(r'E:\grid\churches.db')

# Get existing charity numbers
existing = set()
for row in conn.execute("SELECT cra_bn FROM churches WHERE source=? AND cra_bn IS NOT NULL", (SOURCE,)).fetchall():
    if row[0]:
        existing.add(row[0])

imported = 0
skipped = 0
for r in religious:
    num = r.get('number', '')
    if num in existing:
        skipped += 1
        continue
    
    faith = faith_map.get(r.get('faith', ''), 'Other')
    denom = r.get('denomination')
    lm_type = r.get('landmark_type', 'church')
    name = (r.get('name') or '')[:200]
    address = (r.get('address') or '')[:200]
    purpose = (r.get('purpose') or '')[:500]
    
    # Parse city from Irish address
    city = None
    if address:
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            city = parts[-2]
    
    try:
        conn.execute("""
            INSERT INTO churches (name, faith, denomination, city, country,
                address, landmark_type, source, cra_bn, last_updated)
            VALUES (?, ?, ?, ?, 'Ireland', ?, ?, ?, ?, date('now'))
        """, (name, faith, denom, city, address, lm_type, SOURCE, num))
        imported += 1
        if imported % 100 == 0:
            conn.commit()
            print(f"  Imported {imported}...")
    except Exception as e:
        print(f"  ERROR: {name[:40]}: {e}")
        skipped += 1

conn.commit()

print(f"\n{'='*60}")
print(f"IMPORT COMPLETE")
print(f"{'='*60}")
print(f"  Classified: {len(classified)}")
print(f"  Religious:  {len(religious)}")
print(f"  Imported:   {imported}")
print(f"  Skipped:    {skipped}")

# Sample
if imported > 0:
    samples = conn.execute(
        "SELECT name, faith, denomination, city FROM churches WHERE source=? AND cra_bn IS NOT NULL LIMIT 10",
        (SOURCE,)
    ).fetchall()
    print("\n  Samples:")
    for s in samples:
        print(f"    {s[0][:50]:50s} | {s[1]:12s} | {s[2] or '-':20s} | {s[3] or '-'}")

conn.close()

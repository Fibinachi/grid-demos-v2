"""
Import Ireland religious charities directly from DeepSeek checkpoint.
The checkpoint already has merged XLSX data (address, number, etc.).
"""
import json, sys, time, urllib.request
sys.path.insert(0, r'E:\grid')
from gw_db import connect

CHECKPOINT = r'E:\grid\data\ireland_religious_classified.json'
SOURCE = 'ireland_charities_register'

faith_map = {
    'christian': 'Christian', 'muslim': 'Islam', 'jewish': 'Judaism',
    'hindu': 'Hindu', 'buddhist': 'Buddhist', 'sikh': 'Sikh',
    'other_religious': 'Other',
}

# Load checkpoint
classified = json.load(open(CHECKPOINT))
print(f"Checkpoint entries: {len(classified)}")

# Filter religious
religious = [r for r in classified 
             if r.get('faith') and r['faith'] != 'non_religious' 
             and r.get('confidence', 0) >= 0.5]

print(f"Religious: {len(religious)}")

faith_counts = {}
for r in religious:
    f = faith_map.get(r.get('faith', ''), 'Other')
    faith_counts[f] = faith_counts.get(f, 0) + 1
for f, c in sorted(faith_counts.items(), key=lambda x: -x[1]):
    print(f"  {f}: {c}")

# Connect to DB
conn = connect(r'E:\grid\churches.db')

# Get existing charity numbers to avoid dupes
existing = set()
for row in conn.execute("SELECT cra_bn FROM churches WHERE source=? AND cra_bn IS NOT NULL", (SOURCE,)).fetchall():
    if row[0]:
        existing.add(row[0])

# Check how many we already have
existing_all = set()
for row in conn.execute("SELECT cra_bn FROM churches WHERE cra_bn IS NOT NULL").fetchall():
    if row[0]:
        existing_all.add(row[0])

overlap = existing_all & {r.get('number', '') for r in religious if r.get('number')}
print(f"\nExisting Irish charity numbers in DB: {len(existing_all)}")
print(f"Overlap with our religious list: {len(overlap)}")
print(f"Actually from this source: {len(existing)}")

# Import
imported = 0
skipped_existing = 0
skipped_other = 0

for r in religious:
    num = r.get('number', '')
    if not num:
        skipped_other += 1
        continue
    if num in existing_all:
        skipped_existing += 1
        continue
    
    faith = faith_map.get(r.get('faith', ''), 'Other')
    denom = r.get('denomination')
    lm_type = r.get('landmark_type', 'church')
    name = (r.get('name') or '')[:200]
    address = (r.get('address') or '')[:200]
    
    # Parse city from Irish address (last comma-separated part before county)
    city = None
    if address:
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            city = parts[-2]  # Second-to-last is usually the town
    
    try:
        conn.execute("""
            INSERT INTO churches (
                name, faith, denomination, city, country,
                address, landmark_type, source, cra_bn, last_updated
            ) VALUES (?, ?, ?, ?, 'Ireland', ?, ?, ?, ?, date('now'))
        """, (name, faith, denom, city, address, lm_type, SOURCE, num))
        imported += 1
        
        if imported % 200 == 0:
            conn.commit()
            print(f"  Imported {imported}...")
            
    except Exception as e:
        print(f"  ERROR: {name[:40]}: {e}")
        skipped_other += 1

conn.commit()

print(f"\n{'='*60}")
print(f"IMPORT COMPLETE")
print(f"{'='*60}")
print(f"  Religious classified: {len(religious)}")
print(f"  Imported:             {imported}")
print(f"  Skipped (existing):   {skipped_existing}")
print(f"  Skipped (other):      {skipped_other}")

# Samples
if imported > 0:
    samples = conn.execute(
        "SELECT name, faith, denomination, city FROM churches WHERE source=? ORDER BY id DESC LIMIT 15",
        (SOURCE,)
    ).fetchall()
    print("\n  Sample imports:")
    for s in samples:
        print(f"    {s[0][:50]:50s} | {s[1]:12s} | {s[2] or '-':20s} | {s[3] or '-'}")

conn.close()

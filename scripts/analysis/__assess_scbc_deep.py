"""Deep analysis of SCBC overlap with existing DB."""
import json
import re
import sqlite3
import random

db = sqlite3.connect('E:/grid/churches.db')

with open('data/scbc_algolia_all.json') as f:
    churches = json.load(f)

def parse_content(c):
    content = c.get('content', '')
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    result = {
        'name': c['post_title'],
        'address': lines[0] if lines else '',
        'city': '',
        'lat': c.get('_geoloc', {}).get('lat'),
        'lon': c.get('_geoloc', {}).get('lng'),
    }
    if len(lines) > 1 and ',' in lines[1]:
        result['city'] = lines[1].split(',')[0].strip()
    return result

# Load all SC churches
existing = db.execute("""
    SELECT id, name, normalized_name, address, city, zip, latitude, longitude,
           denomination, source, faith, tradition
    FROM churches WHERE country = 'US' AND state = 'SC'
""").fetchall()
print(f"Existing SC churches in DB: {len(existing)}")

# Build address lookup
addr_map = {}
for row in existing:
    eid, ename, ename_norm, eaddr, ecity, ezip, elat, elon, edenom, esource, efaith, etrad = row
    if eaddr:
        addr_map[eaddr.lower().strip()] = (eid, edenom, esource, efaith, etrad)

# For each SCBC church, check what's in DB
matched_sbc = 0
matched_not_sbc = []
matched_no_denom = 0
new_churches = []

for c in churches:
    info = parse_content(c)
    addr = info['address'].lower().strip()
    
    if addr in addr_map:
        eid, edenom, esource, efaith, etrad = addr_map[addr]
        if edenom and ('baptist' in edenom.lower() or 'sbc' in edenom.lower()):
            matched_sbc += 1
        elif edenom:
            matched_not_sbc.append((info['name'], info['address'], edenom, esource, efaith, etrad))
        else:
            matched_no_denom += 1
    else:
        new_churches.append(info)

print(f"\n=== Match Results ===")
print(f"  Matched & already SBC:     {matched_sbc}")
print(f"  Matched but DIFFERENT denom: {len(matched_not_sbc)}")
print(f"  Matched but no denomination: {matched_no_denom}")
print(f"  Not in DB (new):           {len(new_churches)}")
print(f"  TOTAL:                     {matched_sbc + len(matched_not_sbc) + matched_no_denom + len(new_churches)}")

print(f"\n=== Matched but NOT SBC ({len(matched_not_sbc)}) ===")
for name, addr, denom, source, faith, trad in sorted(matched_not_sbc, key=lambda x: x[2])[:25]:
        print(f"  {name}")
        print(f"    {addr} | denom={denom} | source={source} | faith={faith} | trad={trad}")

# Source breakdown for non-SBC matches
print(f"\n=== By source ===")
src_counts = {}
for _, _, _, source, _, _ in matched_not_sbc:
    src = source or 'NULL'
    src_counts[src] = src_counts.get(src, 0) + 1
for src, cnt in sorted(src_counts.items(), key=lambda x: -x[1]):
    print(f"  {src}: {cnt}")

# Denomination breakdown for non-SBC matches
print(f"\n=== By denomination ===")
denom_counts = {}
for _, _, denom, _, _, _ in matched_not_sbc:
    denom_counts[denom] = denom_counts.get(denom, 0) + 1
for d, cnt in sorted(denom_counts.items(), key=lambda x: -x[1])[:20]:
    print(f"  {d}: {cnt}")

# Fuzzy check for "new" churches
print(f"\n=== Fuzzy check: 200 random 'new' churches by name match ===")
sample = random.sample(new_churches, min(200, len(new_churches)))
fuzzy_found = 0
for info in sample:
    name = info['name'].lower().strip()[:25]
    cur = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country = 'US' AND state = 'SC' 
        AND (LOWER(name) LIKE ? OR LOWER(normalized_name) LIKE ?)
    """, (f'%{name}%', f'%{name}%'))
    cnt = cur.fetchone()[0]
    if cnt > 0:
        fuzzy_found += 1

print(f"  Fuzzy-matched {fuzzy_found}/{len(sample)} by partial name")

db.close()

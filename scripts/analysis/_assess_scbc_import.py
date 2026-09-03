"""Assess SCBC Algolia data for import into GRID database."""
import json
import re
import sqlite3
from collections import Counter

DATA_FILE = 'data/scbc_algolia_all.json'
DB_PATH = 'E:/grid/churches.db'

def parse_content(c):
    """Parse the content field to extract structured info."""
    content = c.get('content', '')
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    
    result = {
        'algolia_id': c['objectID'],
        'name': c['post_title'],
        'url': c['permalink'],
        'lat': c.get('_geoloc', {}).get('lat'),
        'lon': c.get('_geoloc', {}).get('lng'),
        'address': '',
        'city': '',
        'state': 'SC',
        'zip': '',
        'email': '',
        'phone': '',
        'website': '',
    }
    
    if not lines:
        return result
    
    result['address'] = lines[0]
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        if line == 'Home':
            continue
            
        if ',' in line and len(line) < 60:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                result['city'] = parts[0]
                rest = parts[1].strip()
                m = re.match(r'([A-Za-z ]+?)\s+(\d{5}(?:-\d{4})?)$', rest)
                if m:
                    result['state'] = m.group(1).strip()
                    result['zip'] = m.group(2)
                else:
                    result['state'] = rest
                continue
                
        if '@' in line and ('.com' in line or '.org' in line or '.net' in line or '.edu' in line):
            result['email'] = line
            continue
            
        if re.search(r'[\d\-\(\)\.]{7,}', line) and not line.startswith('http') and not line.startswith('www.'):
            result['phone'] = line
            continue
            
        if line.startswith('http') or line.startswith('www.'):
            result['website'] = line
            continue
    
    return result

# Load data
with open(DATA_FILE) as f:
    churches = json.load(f)

print(f"Total SCBC churches in Algolia: {len(churches)}")

# Parse all
print("Parsing content fields...")
parsed = [parse_content(c) for c in churches]

# Stats
print(f"\n=== Data Quality ===")
print(f"With coordinates: {sum(1 for p in parsed if p['lat'] and p['lon'])}")
print(f"With address:     {sum(1 for p in parsed if p['address'])}")
print(f"With city:        {sum(1 for p in parsed if p['city'])}")
print(f"With zip:         {sum(1 for p in parsed if p['zip'])}")
print(f"With email:       {sum(1 for p in parsed if p['email'])}")
print(f"With phone:       {sum(1 for p in parsed if p['phone'])}")
print(f"With website:     {sum(1 for p in parsed if p['website'])}")

# Match against DB using bulk lookup
print(f"\n=== Matching Against DB ===")
db = sqlite3.connect(DB_PATH)

# Bulk load all SC church addresses
print("Loading existing SC churches from DB...")
existing = db.execute("""
    SELECT id, name, normalized_name, address, city, zip, latitude, longitude,
           denomination, source 
    FROM churches WHERE country = 'US' AND state = 'SC'
""").fetchall()
print(f"Existing SC churches in DB: {len(existing)}")

# Build lookup sets
existing_addresses = set()
existing_name_city = {}  # (name_normalized, city) -> id
for row in existing:
    eid, ename, ename_norm, eaddr, ecity, ezip, elat, elon, edenom, esource = row
    if eaddr:
        existing_addresses.add(eaddr.lower().strip())
    key = (ename.lower().strip(), ecity.lower().strip()) if ecity else None
    if key:
        existing_name_city[key] = eid
    # Also by normalized name
    if ename_norm and ecity:
        key2 = (ename_norm.lower().strip(), ecity.lower().strip())
        if key2 not in existing_name_city:
            existing_name_city[key2] = eid

# Match
matched_by_address = 0
matched_by_name_city = 0
new_parsed = []

for p in parsed:
    if p['address'] and p['address'].lower().strip() in existing_addresses:
        matched_by_address += 1
        continue
    
    if p['name'] and p['city']:
        key = (p['name'].lower().strip(), p['city'].lower().strip())
        if key in existing_name_city:
            matched_by_name_city += 1
            continue
    
    new_parsed.append(p)

print(f"Matched by address: {matched_by_address}")
print(f"Matched by name+city: {matched_by_name_city}")
print(f"NEW churches to import: {len(new_parsed)}")

# Show new churches
if new_parsed:
    print(f"\n=== Sample of {min(20, len(new_parsed))} new churches ===")
    for p in new_parsed[:20]:
        print(f"  {p['name']}")
        print(f"    {p['address']}, {p['city']}, {p['state']} {p['zip']}")
        print(f"    Lat/Lon: {p['lat']}, {p['lon']}")
        if p['email']: print(f"    Email: {p['email']}")
        if p['phone']: print(f"    Phone: {p['phone']}")
        if p['website']: print(f"    Web: {p['website']}")
        print()

    # City stats for new churches
    city_counts = Counter(p['city'] for p in new_parsed if p['city'])
    print(f"\n=== New churches by city (top 20) ===")
    for city, cnt in city_counts.most_common(20):
        print(f"  {city}: {cnt}")

# Check which existing SBC churches match
print(f"\n=== Existing SC SBC Denominations ===")
denom_counts = db.execute("""
    SELECT denomination, COUNT(*) as cnt FROM churches 
    WHERE country = 'US' AND state = 'SC' 
    AND denomination IS NOT NULL AND denomination != ''
    GROUP BY denomination ORDER BY cnt DESC
    LIMIT 30
""").fetchall()
for d, c in denom_counts:
    if 'baptist' in d.lower() or 'sbc' in d.lower():
        print(f"  {d}: {c}")

# Save new churches data
if new_parsed:
    with open('data/scbc_new_churches.json', 'w') as f:
        json.dump(new_parsed, f, indent=2)
    print(f"\nSaved {len(new_parsed)} new churches to data/scbc_new_churches.json")

db.close()
print("\nDone!")

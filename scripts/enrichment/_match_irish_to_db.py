"""
Match Irish Church Directory parishes against existing churches in churches.db.
"""
import re, csv, sqlite3

# 1. Load and parse the directory
with open('data/irish_directory/full_text.txt', encoding='utf-8') as f:
    text = f.read()

# Split into sections, focus on clergy list
parts = text.split('LIST OF CLERGY')

entries = []
for section_idx in range(1, len(parts)):
    content = parts[section_idx]
    lines = content.split('\n')
    
    buf = ""
    for line in lines:
        line = line.strip()
        if not line or line.startswith('=') or line.isdigit():
            continue
        if line.startswith('ADVERTISING') or line.startswith('LIST OF CLERGY') or len(line) < 5:
            continue
        
        is_new = bool(re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][A-Za-z\s\',\.\-\(\)]+,\s', line))
        
        if is_new and buf:
            entries.append(buf)
            buf = line
        elif is_new and not buf:
            buf = line
        elif buf and line:
            if re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][A-Za-z\']+.*,', line):
                entries.append(buf)
                buf = line
            else:
                buf += ' ' + line

if buf:
    entries.append(buf)

print(f'Total parsed entries: {len(entries)}')

# 2. Extract parish+diocese records
parish_records = []
for entry in entries:
    # Extract diocese
    dioceses = re.findall(r'\(([^)]+)\)', entry)
    # Extract parish (text after position markers I or C before parenthesis)
    parish = ""
    pos_match = re.search(r'\b(I|C|Prebendary|Canon|Chancellor|Precentor|Archdeacon)\s+([A-Z][A-Za-z\s\'\.\-]+?)\s*\(', entry)
    if pos_match:
        parish = pos_match.group(2).strip().rstrip(',').strip()
    
    # Bishop entries
    if not parish:
        bp_match = re.search(r'Lord (Arch)?Bishop of ([A-Za-z\s,]+)', entry)
        if bp_match:
            parish = f"Diocese of {bp_match.group(2).strip()}"
    
    # Location after diocese
    location = ""
    if dioceses:
        last_dio = dioceses[-1]
        # Find the last occurrence
        idx = entry.rfind(f'({last_dio})')
        if idx >= 0:
            after = entry[idx + len(last_dio) + 2:].strip().lstrip(',').strip()
            # Clean up - take first reasonable chunk
            after = re.sub(r'\s+', ' ', after)
            if after and len(after) < 80:
                location = after
    
    if parish and dioceses:
        parish_records.append({
            'parish': parish,
            'diocese': dioceses[-1],
            'location': location,
            'raw': entry[:150]
        })

print(f'Records with parish+diocese: {len(parish_records)}')

# Deduplicate by parish+diocese
seen = set()
unique_parishes = []
for r in parish_records:
    key = (r['parish'].lower().strip(), r['diocese'].lower().strip())
    if key not in seen:
        seen.add(key)
        unique_parishes.append(r)

print(f'Unique parish+diocese pairs: {len(unique_parishes)}')

# Save unique parishes
with open('data/irish_directory/unique_parishes.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['parish', 'diocese', 'location', 'raw'])
    for r in unique_parishes:
        w.writerow([r['parish'], r['diocese'], r['location'], r['raw']])

# 3. Match against churches.db
db = sqlite3.connect('churches.db')
cur = db.cursor()

# Get all Anglican/Church of Ireland churches in Ireland
cur.execute("""
    SELECT id, name, denomination, city, county, diocese, latitude, longitude 
    FROM churches c
    LEFT JOIN church_enrichment e ON c.id = e.church_id
    WHERE c.country='IE' 
    AND (LOWER(c.denomination) LIKE '%anglican%' 
         OR LOWER(c.denomination) LIKE '%church of ireland%'
         OR c.faith = 'Christian')
    AND c.latitude IS NOT NULL
""")
db_churches = cur.fetchall()
print(f'\nAnglican/Christian churches in Ireland DB: {len(db_churches)}')

# Match by parish name (many churches are named after their parish)
matched = 0
parish_names_only = {}

for r in unique_parishes:
    parish_name = r['parish'].lower().strip()
    diocese = r['diocese'].lower().strip()
    
    # Try matching by parish name against church name
    found = False
    for dbc in db_churches:
        db_name = (dbc[1] or '').lower()
        # Check if parish name appears in church name
        if parish_name in db_name or db_name in parish_name:
            # Also check city/county if available
            matched += 1
            if parish_name not in parish_names_only:
                parish_names_only[parish_name] = []
            parish_names_only[parish_name].append({
                'db_id': dbc[0],
                'db_name': dbc[1],
                'db_city': dbc[3],
                'db_diocese': dbc[5],
                'dir_diocese': r['diocese'],
                'dir_location': r['location']
            })
            found = True
            break
    
    if not found:
        # Try city match
        location_lower = r['location'].lower().strip()
        for dbc in db_churches:
            db_city = (dbc[3] or '').lower()
            if location_lower and db_city and (location_lower in db_city or db_city in location_lower):
                matched += 1
                break

print(f'Parish-level matches: {len(parish_names_only)}')
print(f'Total matched references: {matched}')

# Show some matches
print('\nSample matches (first 50):')
count = 0
for parish, matches in sorted(parish_names_only.items()):
    if count >= 50:
        break
    for m in matches[:2]:
        print(f'  "{parish}" -> DB: {m["db_name"]} (id={m["db_id"]}, city={m["db_city"]})')
    count += 1

# Show unmatched parishes
all_matched_parishes = set(parish_names_only.keys())
unmatched = [r for r in unique_parishes if r['parish'].lower().strip() not in all_matched_parishes]
print(f'\nUnmatched parishes: {len(unmatched)}')
for r in unmatched[:30]:
    print(f'  {r["parish"]} ({r["diocese"]}) - loc: {r["location"]}')

# Now try a broader match - just by city/location
print('\n\n=== Broader match by location ===')
location_matches = {}
for r in unique_parishes:
    loc = r['location'].lower().strip()
    if not loc:
        continue
    for dbc in db_churches:
        db_city = (dbc[3] or '').lower()
        if loc == db_city or (len(loc) > 3 and loc in db_city):
            key = r['parish']
            if key not in location_matches:
                location_matches[key] = []
            location_matches[key].append({
                'db_id': dbc[0],
                'db_name': dbc[1],
                'db_city': dbc[3],
                'dir_location': r['location']
            })
            break

print(f'Additional location matches: {len(location_matches)}')

db.close()

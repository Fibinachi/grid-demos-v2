"""Parse Catholic Directory diocese listings and match against DB."""
import re, sqlite3, csv

with open('data/catholic_directory_1907/full_text.txt', encoding='utf-8') as f:
    text = f.read()

# Clean text: collapse broken lines within paragraphs
text = re.sub(r'\n([a-z])', r' \1', text)  # join broken words
text = re.sub(r'-\n', '', text)  # remove hyphenation

# Extract diocese sections
# Pattern: ARCHDIOCESE OF XXXX. or DIOCESE OF XXXX. followed by content
sections = re.split(r'(ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)\.', text)

print(f'Found {len(sections)//3} diocese sections')
# Actually the split creates groups of (header, name, content)
# Let me use finditer instead

diocese_sections = {}
current_dio = None
current_content = []

for line in text.split('\n'):
    line = line.strip()
    # Detect new diocese
    m = re.match(r'^(ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)\.', line)
    if m:
        if current_dio:
            diocese_sections[current_dio] = '\n'.join(current_content)
        current_dio = f'{m.group(1)} OF {m.group(2).strip()}'
        current_content = [line]
    elif current_dio:
        current_content.append(line)

if current_dio:
    diocese_sections[current_dio] = '\n'.join(current_content)

print(f'Parsed {len(diocese_sections)} diocese sections')

# Extract parishes from each diocese
records = []  # (diocese, parish_name, city, state, country)
for dio_name, content in diocese_sections.items():
    # Determine country/region from diocese name
    country = 'US'  # default
    if any(x in dio_name.upper() for x in ['ONTARIO','QUEBEC','TORONTO','MONTREAL','OTTAWA','KINGSTON','LONDON','HAMILTON','ST. BONIFACE','REGINA','ST. JOHN','HALIFAX','VANCOUVER']):
        country = 'CA'
    elif any(x in dio_name.upper() for x in ['DUBLIN','ARMAGH','CASHEL','DUBLIN','TUAM']):
        country = 'IE'
    elif any(x in dio_name.upper() for x in ['WESTMINSTER','LIVERPOOL','BIRMINGHAM','SOUTHWARK','CARDIFF']):
        country = 'GB'
    
    # Extract state from content (e.g., "Comprises all the Counties of Maryland")
    state_m = re.search(r'Comprises all the Counties of ([A-Za-z\s]+)', content)
    state = state_m.group(1).strip() if state_m else ''
    
    # Extract parish names (church listings)
    # Lines starting with ST., ST. X, or Church names
    for line in content.split('\n'):
        line = line.strip()
        # Match church names like "ST. ALPHONSUS' (German), 114 W. Saratoga st."
        # or "THE CATHEDRAL, Cathedral and Mulberry sts."
        church_m = re.match(r'^([A-Z][A-Z\s\'\.\,\-\(\)]+?),\s+(\d+\s+.+?)(?:\.|$)', line)
        if church_m:
            church_name = church_m.group(1).strip().rstrip(',').strip()
            address = church_m.group(2).strip()
            records.append((dio_name, church_name, '', state, country))
        
        # Also match "ST. X, street" patterns
        church_m2 = re.match(r'^([A-Z][A-Z\s\'\.\-]+[A-Z]),\s+(.+?)(?:\.|$)', line)
        if church_m2 and not church_m:
            cn = church_m2.group(1).strip()
            addr = church_m2.group(2).strip()
            # Skip city headers (just city names in caps)
            if not re.match(r'^[A-Z\s]{3,30}$', cn) and len(cn) > 5:
                records.append((dio_name, cn, '', state, country))

print(f'Extracted {len(records)} parish records')

# Save to CSV
with open('data/catholic_directory_1907/parishes.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['diocese', 'parish_name', 'city', 'state', 'country'])
    for r in records:
        w.writerow(r)

# Show sample
print('\nSample records:')
for r in records[:30]:
    print(f'  {r[0]} | {r[1]} | {r[3]} | {r[4]}')

# ===== Match against DB =====
print('\n=== Matching against churches.db ===')
db = sqlite3.connect('churches.db')
cur = db.cursor()

matched = 0
new_potential = 0
for dio, parish, city, state, country in records:
    # Try matching by parish name
    parish_clean = parish.lower().strip().rstrip("'s").rstrip("'")
    cur.execute("""
        SELECT id, name, city, state, country FROM churches 
        WHERE LOWER(name) LIKE ? AND country=?
        LIMIT 1
    """, (f'%{parish_clean}%', country))
    row = cur.fetchone()
    if row:
        matched += 1
    else:
        new_potential += 1

print(f'Matched: {matched}')
print(f'New (not in DB): {new_potential}')

# Show diocese coverage
print('\nDioceses found in 1907 directory:')
for d in sorted(diocese_sections.keys()):
    cnt = sum(1 for r in records if r[0] == d)
    print(f'  {d}: {cnt} parishes')

db.close()

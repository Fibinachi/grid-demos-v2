"""Tag junk entries and identify salvageable ones among ungeocoded Catholic records."""
import sqlite3, re

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Patterns that suggest a real entity (church, school, university, etc.)
real_patterns = [
    r'\bparish\b', r'\bchurch\b', r'\bcathedral\b', r'\bchapel\b',
    r'\buniversity\b', r'\bcollege\b', r'\bschool\b', r'\bacademy\b',
    r'\bseminary\b', r'\bmonastery\b', r'\bconvent\b', r'\babbey\b',
    r'\bshrine\b', r'\bmission\b', r'\bbasilica\b', r'\boratory\b',
    r'\bcatholic center\b', r'\bcatholic centre\b', r'\bpastoral center\b',
    r'\bst\.?\s', r'\bsaint\s', r'\bimmaculate\b', r'\bsacred heart\b',
    r'\bholy\s', r'\bour lady\b', r'\bblessed\b', r'\bchrist the king\b',
    r'\bdioce', r'\barchdioce', r'\beparchy\b', r'\bepiscopal\b',
    r'\bguild\b', r'\bknights\b', r'\bcatholic daughters\b',
    r'\bdepartment\b', r'\boffice of\b', r'\bministry\b',
]

# Patterns that suggest junk (news, articles, prayers, etc.)
junk_patterns = [
    r'^new report', r'^report:', r'^from pigs eye', r'^\d{4}',
    r'^ministry leaders to examine', r'^amid national',
    r'^as st\.? francis said', r'^st\.? patricks day dispensation',
    r'act of hope', r'act of ', r'prayer o lord', r'for strength in',
    r'you are christ', r'holy spirit prayer', r'\.{3,}',  # ellipsis
    r'unveils? \d', r'economic impact', r'billion',
    r'merge to form', r'merger? of',
    r'^how to', r'^what is', r'^why ', r'^when ',
]

# Get ungeocoded
c.execute("""SELECT id, name, address, city, state, source, denomination
  FROM churches
  WHERE country='US' 
  AND (LOWER(denomination) LIKE '%catholic%' OR LOWER(denomination) LIKE '%roman%')
  AND (latitude IS NULL OR longitude IS NULL)
""")
rows = c.fetchall()

keep = []
junk = []
universities = []

for row in rows:
    rid, name, addr, city, state, source, denom = row
    name_lower = (name or '').lower()
    
    # Catholic universities are always real
    if source == 'wikipedia_catholic_uni' or 'university' in name_lower:
        keep.append(('university', rid, name))
        universities.append(row)
        continue
    
    # Has address or city - likely real
    has_addr = addr and addr.strip()
    has_city = city and city.strip()
    if has_addr or has_city:
        keep.append(('has_location', rid, name))
        continue
    
    # Check junk patterns
    is_junk = False
    for pat in junk_patterns:
        if re.search(pat, name_lower):
            junk.append(('junk_pattern', rid, name))
            is_junk = True
            break
    if is_junk:
        continue
    
    # Check real patterns
    is_real = False
    for pat in real_patterns:
        if re.search(pat, name_lower):
            keep.append(('real_pattern', rid, name))
            is_real = True
            break
    if is_real:
        continue
    
    # Unclear
    junk.append(('unclear', rid, name))

print(f"Universities: {len(universities)}")
print(f"Keep (real patterns): {len([k for k in keep if k[0]=='real_pattern'])}")
print(f"Keep (has location): {len([k for k in keep if k[0]=='has_location'])}")
print(f"Junk (patterns): {len([j for j in junk if j[0]=='junk_pattern'])}")
print(f"Junk (unclear/no name): {len([j for j in junk if j[0]=='unclear'])}")
print(f"\nTotal keep: {len(keep)}, Total junk: {len(junk)}")

# Show universities
print("\n=== Catholic Universities ===")
for r in universities:
    print(f'  {r[0]:>8} {str(r[1] or ""):50s} {str(r[3] or ""):20s} {r[4]}')

# Show some keep examples
print("\n=== Keep samples (real patterns) ===")
count = 0
for _, cat, rid, name in keep:
    if cat == 'real_pattern' and count < 15:
        print(f'  {rid:>8} {str(name or ""):60s}')
        count += 1

# Show some junk examples  
print("\n=== Junk samples ===")
count = 0
for _, cat, rid, name in junk:
    if count < 10:
        print(f'  {rid:>8} [{cat}] {str(name or ""):70s}')
        count += 1

conn.close()

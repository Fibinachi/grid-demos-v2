"""
Parse Catholic Directory (1907) — extract ALL institution types as hierarchical records.
Churches, schools, orphanages, hospitals, colleges, convents, etc.
Each sub-institution linked to its governing parish/church.
"""
import re, csv, os
from tqdm import tqdm

OUT_DIR = 'data/catholic_directory_1907'
os.makedirs(OUT_DIR, exist_ok=True)

print('=== Loading text ===')
with open(f'{OUT_DIR}/full_text.txt', encoding='utf-8') as f:
    text = f.read()
print(f'  {len(text):,} chars, {text.count(chr(10)):,} lines')

# Clean: join broken words split across lines (lowercase continuation)
text = re.sub(r'-\n([a-z])', r'\1', text)

# ============================================================
# STEP 1: Identify all diocese sections
# ============================================================
print('\n=== Identifying diocese sections ===')

# Find all CLERGY, CHURCHES, MISSIONS AND SCHOOLS. boundaries
section_starts = [m.end() for m in re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', text)]

print(f'Found {len(section_starts)} section boundaries')

# For each section, find which diocese it belongs to by looking backwards
section_dioceses = []
for i, sec_start in enumerate(section_starts):
    # Look backwards up to 3000 chars for a diocese header
    ctx = text[max(0, sec_start - 3000):sec_start]
    # Find the LAST (ARCH)DIOCESE OF... header before the section
    hdrs = re.findall(r'((?:ARCH)?DIOCESE)\s+OF\s+([A-Z][A-Z\s\.\-\']+?)(?:\.|\n)', ctx, re.IGNORECASE)
    if hdrs:
        dtype, dname = hdrs[-1]
        dname = dname.strip().rstrip('.')
        section_dioceses.append(f'{dtype} OF {dname}')
    else:
        # Try PROVINCE OF or VICARIATE-APOSTOLIC
        provs = re.findall(r'(PROVINCE\s+OF\s+[A-Z][A-Z\s\.\-]+)', ctx)
        if provs:
            section_dioceses.append(provs[-1].strip())
        else:
            vicars = re.findall(r'((?:VICARIATE|PREFECTURE)[\- ]+APOSTOLIC\s+OF\s+[A-Z][A-Z\s\.\-]+)', ctx, re.IGNORECASE)
            if vicars:
                section_dioceses.append(vicars[-1].strip().upper())
            else:
                section_dioceses.append(f'SECTION_{i+1}')

for i, d in enumerate(section_dioceses):
    print(f'  Section {i+1}: {d}')

# ============================================================
# STEP 2: Parse each section for institutions
# ============================================================
print('\n=== Parsing institutions ===')

# Institution type patterns (in order of priority)
INST_PATTERNS = [
    ('orphanage', re.compile(r'([A-Z][A-Za-z\'\.,]+\s+(?:Orphan\s+)?(?:Asylum|Orphanage|Home\s+for\s+Orphans))', re.IGNORECASE)),
    ('hospital', re.compile(r'([A-Z][A-Za-z\'\.,]+\s+(?:Hospital|Infirmary|Sanitarium))', re.IGNORECASE)),
    ('college', re.compile(r'([A-Z][A-Za-z\'\.,]+\s+(?:College|Academy|University|Institute|Seminary)(?:\s+[A-Z][A-Za-z]*)?)')),
    ('convent', re.compile(r'([A-Z][A-Za-z\'\.,]+\s+(?:Convent|Monastery|Novitiate|Motherhouse|Provincial\s+House))', re.IGNORECASE)),
]

def get_country_for_diocese(dio_name):
    """Guess country from diocese name"""
    up = dio_name.upper()
    if any(x in up for x in ['QUEBEC', 'ONTARIO', 'TORONTO', 'MONTREAL', 'OTTAWA', 'VANCOUVER',
                               'ST. BONIFACE', 'HALIFAX', 'REGINA', 'SAINT JOHN', 'LONDON',
                               'KINGSTON', 'HAMILTON', 'CHATHAM', 'ALEXANDRIA', 'NICOLET',
                               'PEMBROKE', 'PETERBOROUGH', 'SHERBROOKE', 'ST. GEORGE',
                               'MACKENZIE', 'KEEWATIN', 'ST. ALBERT', 'PRINCE ALBERT',
                               'SASKATOON', 'ST. JAMES', 'VANCOUVER ISLAND']):
        return 'CA'
    if any(x in up for x in ['DUBLIN', 'ARMAGH', 'CASHEL', 'TUAM', 'KILLARNEY', 'KILDARE',
                               'MEATH', 'OSSORY', 'CLOGHER', 'CLONFERT', 'ELPHIN', 'FERNS',
                               'KILMORE', 'LIMERICK', 'RAPHOE', 'WATERFORD', 'GALWAY',
                               'KILFENORA', 'KERRY', 'ACHONRY', 'ARDAGH', 'DROMORE',
                               'DERRY', 'DOWN', 'ROSS', 'DROMORE']):
        return 'IE'
    if any(x in up for x in ['WESTMINSTER', 'LIVERPOOL', 'BIRMINGHAM', 'SOUTHWARK',
                               'CARDIFF', 'HEXHAM', 'NEWCASTLE', 'SALFORD', 'SHREWSBURY',
                               'NORTHAMPTON', 'NOTTINGHAM', 'PORTSMOUTH', 'BRENTWOOD',
                               'CLIFTON', 'LEEDS', 'LANCASTER', 'MIDDLESBROUGH',
                               'PLYMOUTH', 'WALES', 'MENEVE']):
        return 'GB'
    if any(x in up for x in ['GUATEMALA', 'PORT OF SPAIN', 'MEXICO', 'CENTRAL AMERICA']):
        return 'OTHER'
    # Default US for unknown
    return 'US'

def parse_diocese_section(dio_name, section_text, section_num):
    """Parse a single diocese section into institution records."""
    records = []
    country = get_country_for_diocese(dio_name)
    
    # State tracking for line-by-line parsing
    current_city = ''
    current_church = None  # (name, address)
    current_parent_type = 'diocese'
    
    lines = section_text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines, page markers, recapitulation, religious communities
        if not line or line.startswith('===') or line.startswith('RECAPITULATION') or line.startswith('RELIGIOUS COMMUNITIES'):
            if line.startswith('RECAPITULATION') or line.startswith('RELIGIOUS COMMUNITIES'):
                # Stop parsing when we hit these sections
                break
            i += 1
            continue
        
        # Skip administrative headers and clergy listings
        if any(line.startswith(x) for x in ['Vicar-', 'Chancellor', 'Secretary', 'Consultors', 
                                              'Examiners', 'Examinatores', 'Procurator',
                                              'Auditor', 'Defensor', 'Deans', 'Curia',
                                              'Former Bishops', 'FormerBishops', 'Residence',
                                              'Bishop\'s', 'Theological']):
            i += 1
            continue
        
        # Skip lines that are just clergy names/addresses with Rev./Rt./Very Rev./Mt.
        if re.match(r'^(Rev\.|Rt\.|Very\s+Rev\.|Mt\.|Most\s+Rev\.|Right\s+Rev\.|RightRev)', line):
            i += 1
            continue
        
        # Skip lines that are just names with D.D. or S.T.L. etc.
        if re.match(r'^[A-Z][A-Za-z\.\'\s]+,\s*(?:D\.D\.|S\.T\.L\.|S\.J\.|O\.S\.B\.|C\.S\.S\.R\.|O\.M\.I\.|C\.M\.|O\.F\.M\.|O\.P\.|C\.S\.B\.|S\.S\.)', line):
            i += 1
            continue
        
        # Detect city header: "CITY OF X." or "OUTSIDE OF THE CITY OF X." or just "X." in caps
        city_m = re.match(r'^(?:CITY\s+OF\s+|OUTSIDE\s+OF\s+(?:THE\s+)?CITY\s+OF\s+)?([A-Z][A-Z\s\.\-]+?)\.?$', line)
        if city_m and len(line) < 60 and not ',' in line:
            city_candidate = city_m.group(1).strip().rstrip('.')
            # Reject if it looks like a church name (contains ' or common church words)
            if not any(x in city_candidate.upper() for x in ["'S", 'CHURCH', 'CATHEDRAL', 'ST.', 'OUR ', 'HOLY', 'SACRED', 'IMMACULATE', 'BLESSED']):
                current_city = city_candidate.title()
                current_church = None
                i += 1
                continue
        
        # Detect church/parish entry: ALL CAPS name with comma + address
        # Patterns: "ST. X'S, address", "THE CATHEDRAL, address", "SACRED HEART, address"
        church_m = re.match(r"^((?:ST\.|SAINT|THE|OUR\s+(?:LADY|LADY\s+OF)|HOLY|SACRED|IMMACULATE|BLESSED|CORPUS\s+CHRISTI|FOURTEEN|SS\.|ST\.\s+[A-Z]+'S|[A-Z][A-Z\s\.\-]+(?:CHURCH|CATHEDRAL|BASILICA|SHRINE|ABBEY|MISSION))[A-Z\s\'\.\,\-\(\)]*(?:'S)?)\s*,\s*(.+?)$", line)
        
        if church_m:
            church_name = church_m.group(1).strip().rstrip(',').strip()
            church_addr = church_m.group(2).strip()
            # Clean up common OCR artifacts
            church_addr = re.sub(r'\s{2,}', ' ', church_addr)
            church_addr = re.sub(r'\.{2,}', '.', church_addr)
            
            # Reject if it's actually a school/college line
            if any(x in church_name.upper() for x in ['SCHOOL', 'COLLEGE', 'ACADEMY', 'CONVENT']):
                # This is a sub-institution, not a church
                inst_type = 'school' if 'SCHOOL' in church_name.upper() else 'college'
                records.append({
                    'diocese': dio_name, 'city': current_city,
                    'name': church_name, 'address': church_addr,
                    'type': inst_type, 'parent_name': current_church[0] if current_church else '',
                    'parent_type': 'church' if current_church else 'diocese',
                    'country': country, 'section': section_num
                })
                i += 1
                continue
            
            current_church = (church_name, church_addr)
            records.append({
                'diocese': dio_name, 'city': current_city,
                'name': church_name, 'address': church_addr,
                'type': 'church', 'parent_name': dio_name,
                'parent_type': 'diocese',
                'country': country, 'section': section_num
            })
            i += 1
            continue
        
        # Also detect church names without comma (name on its own line, address next)
        church_m2 = re.match(r"^((?:ST\.|SAINT|THE|OUR\s+(?:LADY|LADY\s+OF)|HOLY|SACRED|IMMACULATE|BLESSED|CORPUS\s+CHRISTI|SS\.)[A-Z\s\'\.\,\-\(\)]*(?:'S)?)$", line)
        if church_m2 and not ',' in line and len(line) < 80:
            cn = church_m2.group(1).strip().rstrip(',').strip()
            if not any(x in cn.upper() for x in ['SCHOOL', 'COLLEGE', 'ACADEMY', 'CONVENT', 'HOSPITAL', 'ASYLUM', 'ORPHAN', 'HOME', 'SEMINARY']):
                # Check next line for address
                if i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    addr_m = re.match(r'^(?:Res\.,\s*)?(\d+\s+.+|.+?st\.,|.+?ave\.)', next_line)
                    if addr_m or re.match(r'^[A-Z][a-z]', next_line):
                        current_church = (cn, next_line[:80])
                        records.append({
                            'diocese': dio_name, 'city': current_city,
                            'name': cn, 'address': next_line[:80],
                            'type': 'church', 'parent_name': dio_name,
                            'parent_type': 'diocese',
                            'country': country, 'section': section_num
                        })
                        i += 2
                        continue
        
        # Detect school/college/convent entries (under a church)
        # Pattern: "School-..." or "Schools-..." or "6 Sisters of X..."
        school_m = re.match(r'^(?:School[s]?[\s\-–,]*)?(\d*\s*[A-Z][A-Za-z\s\'\.]*(?:Sisters|Brothers|Fathers|Nuns|Sisters\s+of|Brothers\s+of|School\s+Sisters|Felician|Benedictine|Christian|Franciscan|Ursuline|Presentation|Religious|Jesuit|Oblate|Dominican|Carmelite|Salesian|Marist|La Salette|Josephite|Missionaries|Clerics|Sisters\s+de|Little\s+Sisters|Sisters\s+Servants|Sisters\s+of\s+Charity|Sisters\s+of\s+Mercy|Sisters\s+of\s+St\.|Sisters\s+of\s+the\s+Holy|Sisters\s+of\s+Notre|Sisters\s+of\s+the\s+Presentation|Sisters\s+of\s+Providence|Sisters\s+of\s+the\s+Good|Sisters\s+of\s+the\s+Sacred|Sisters\s+of\s+Christian|Sisters\s+of\s+Jesus|Sisters\s+of\s+Loreto|Sisters\s+of\s+Misericorde))', line)
        if school_m and current_church:
            order_name = school_m.group(1).strip()
            if len(order_name) > 5 and not re.match(r'^\d+$', order_name):
                # Extract address if present
                addr = ''
                addr_m = re.search(r'\(([^)]+)\)', line)
                if addr_m:
                    addr = addr_m.group(1)
                records.append({
                    'diocese': dio_name, 'city': current_city,
                    'name': order_name, 'address': addr,
                    'type': 'school', 'parent_name': current_church[0],
                    'parent_type': 'church',
                    'country': country, 'section': section_num
                })
                i += 1
                continue
        
        # Detect standalone institutions (orphanages, hospitals, etc.)
        # Pattern: "St. X's Orphan Asylum" or "St. X's Hospital"
        for inst_type, pattern in INST_PATTERNS:
            m = pattern.match(line)
            if m:
                inst_name = m.group(1).strip()
                # Get address from the rest of the line
                rest = line[m.end():].strip()
                addr_m2 = re.search(r'((?:\d+\s+.+?|.+?(?:st\.|ave\.|road|place|square|park))(?:\s*\.|$))', rest)
                addr = addr_m2.group(1).strip().rstrip('.') if addr_m2 else ''
                records.append({
                    'diocese': dio_name, 'city': current_city,
                    'name': inst_name, 'address': addr,
                    'type': inst_type, 'parent_name': current_church[0] if current_church else dio_name,
                    'parent_type': 'church' if current_church else 'diocese',
                    'country': country, 'section': section_num
                })
                i += 1
                break
        else:
            i += 1
    
    return records

# Parse all sections
all_records = []
for i, sec_start in enumerate(tqdm(section_starts, desc='Parsing sections')):
    # Determine section end
    if i + 1 < len(section_starts):
        sec_end = section_starts[i + 1]
        # But also stop at RECAPITULATION or RELIGIOUS COMMUNITIES within this range
        section_text = text[sec_start:sec_end]
        # Trim at RECAPITULATION if present
        recap_pos = section_text.find('RECAPITULATION')
        if recap_pos > 0:
            section_text = section_text[:recap_pos]
        # Trim at RELIGIOUS COMMUNITIES if present
        rel_pos = section_text.find('RELIGIOUS COMMUNITIES')
        if rel_pos > 0:
            section_text = section_text[:rel_pos]
    else:
        section_text = text[sec_start:]
    
    dio_name = section_dioceses[i] if i < len(section_dioceses) else f'SECTION_{i+1}'
    records = parse_diocese_section(dio_name, section_text, i + 1)
    all_records.extend(records)

print(f'\nTotal records extracted: {len(all_records):,}')

# ============================================================
# STEP 3: Summarize
# ============================================================
print('\n=== Summary by type ===')
type_counts = {}
for r in all_records:
    t = r['type']
    type_counts[t] = type_counts.get(t, 0) + 1
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c:,}')

print(f'\n=== Summary by diocese ===')
dio_counts = {}
for r in all_records:
    d = r['diocese']
    dio_counts[d] = dio_counts.get(d, 0) + 1
for d, c in sorted(dio_counts.items(), key=lambda x: -x[1]):
    print(f'  {d}: {c:,}')

# ============================================================
# STEP 4: Save to CSV
# ============================================================
print('\n=== Saving to CSV ===')
csv_path = f'{OUT_DIR}/institutions.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['diocese', 'city', 'name', 'address', 'type', 
                                        'parent_name', 'parent_type', 'country', 'section'])
    w.writeheader()
    for r in all_records:
        w.writerow(r)
print(f'Saved to {csv_path}')

# Also save per-type CSVs
for inst_type in type_counts:
    csv_type_path = f'{OUT_DIR}/{inst_type}s.csv'
    with open(csv_type_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['diocese', 'city', 'name', 'address', 'type',
                                            'parent_name', 'parent_type', 'country', 'section'])
        w.writeheader()
        for r in all_records:
            if r['type'] == inst_type:
                w.writerow(r)
    print(f'Saved {csv_type_path} ({type_counts[inst_type]:,} records)')

print('\nDone!')

"""
Parse Irish Church Directory clergy entries into structured fields.
Extract parish+diocese data for matching against churches.db.
"""
import re
import csv

with open('data/irish_directory/full_text.txt', encoding='utf-8') as f:
    text = f.read()

# Split into sections
parts = text.split('LIST OF CLERGY')

# Parse each clergy entry
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
        
        # New entry: starts with name pattern
        is_new = bool(re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][A-Za-z\s\',\.\-\(\)]+,\s', line))
        
        if is_new and buf:
            entries.append(buf)
            buf = line
        elif is_new and not buf:
            buf = line
        elif buf and line:
            # Continuation or new entry
            if re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][A-Za-z\']+.*,', line):
                entries.append(buf)
                buf = line
            else:
                buf += ' ' + line

if buf:
    entries.append(buf)

print(f'Total entries: {len(entries)}')

# Extract structured fields
records = []
parishes = set()

for entry in entries:
    # Extract diocese (text in parentheses)
    dioceses = re.findall(r'\(([^)]+)\)', entry)
    
    # Extract position markers
    is_incumbent = ' I ' in entry or entry.startswith('I ') or ' I\t' in entry
    is_curate = ' C ' in entry or ' C\t' in entry
    is_archdeacon = 'Archdeacon' in entry
    is_dean = 'Dean' in entry or 'Dean ' in entry
    is_canon = 'Canon' in entry or 'Prebendary' in entry or 'Precentor' in entry or 'Chancellor' in entry
    is_bishop = 'Bishop' in entry or 'Archbishop' in entry
    
    # Extract parish name after position marker
    parish = ""
    pos_match = re.search(r'\b(I|C)\s+([A-Z][A-Za-z\s\'\.\-]+?)\s*\(', entry)
    if pos_match:
        parish = pos_match.group(2).strip().rstrip(',')
    elif not pos_match:
        # Try "I ParishName (Diocese)" pattern
        pos_match2 = re.search(r'\bI\s+([A-Z][A-Za-z\s\'\.\-]+?)\s*\(', entry)
        if pos_match2:
            parish = pos_match2.group(1).strip().rstrip(',')
    
    # Extract post town / location (after diocese)
    location = ""
    if dioceses:
        last_dio = dioceses[-1]
        dio_idx = entry.rfind(f'({last_dio})')
        after_dio = entry[dio_idx + len(last_dio) + 2:].strip().lstrip(',').strip()
        if after_dio and len(after_dio) < 100:
            location = after_dio.rstrip(',')
    
    records.append({
        'raw': entry[:200],
        'dioceses': '; '.join(dioceses),
        'is_incumbent': is_incumbent,
        'is_curate': is_curate,
        'parish': parish,
        'location': location,
    })
    
    if parish:
        parishes.add(parish)

print(f'Unique parishes: {len(parishes)}')
print(f'Records with parish: {sum(1 for r in records if r["parish"])}')
print(f'Records with diocese: {sum(1 for r in records if r["dioceses"])}')

# Show unique dioceses
dioceses_set = set()
for r in records:
    for d in r['dioceses'].split('; '):
        if d.strip():
            dioceses_set.add(d.strip())
print(f'\nUnique dioceses ({len(dioceses_set)}):')
for d in sorted(dioceses_set):
    print(f'  {d}')

# Show unique parishes
print(f'\nUnique parishes ({len(parishes)}):')
for p in sorted(parishes)[:50]:
    print(f'  {p}')

# Save to CSV
with open('data/irish_directory/parishes_parsed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['parish', 'dioceses', 'location', 'is_incumbent', 'is_curate'])
    for r in records:
        if r['parish']:
            w.writerow([r['parish'], r['dioceses'], r['location'], r['is_incumbent'], r['is_curate']])

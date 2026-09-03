"""Fix suffragan links with strict scoring-based matching."""
import sqlite3, re
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')
now = datetime.now().isoformat()

# Reset all previous wrong links
db.execute("UPDATE catholic_hierarchy SET parent_id = NULL, parent_cath_type = NULL, "
           "relationship = NULL, archdiocese = NULL WHERE relationship = 'suffragan_of'")
db.commit()
print('Reset previous links')

# Load all territories
territories = {}
for r in db.execute("SELECT id, name, full_name, dio_type, metro_key FROM ecclesiastical_territories"):
    territories[r[0]] = {'name': r[1].lower(), 'full': r[2].lower(), 'type': r[3], 'metro': r[4].lower() if r[4] else None}
print(f'{len(territories)} territories loaded')

# Build code -> best archdiocese name using strict matching
print('\nBuilding code->archdiocese map...')

# For each unique metro code, find the archdiocese whose name best matches
code_usage = {}  # code -> list of (territory_id, territory_name)
for tid, t in territories.items():
    m = t['metro']
    if m and m != '_met':
        if m not in code_usage:
            code_usage[m] = []
        code_usage[m].append(t['name'])

# For archdioceses, generate possible codes
arch_names = {}
for tid, t in territories.items():
    if t['type'] in ('a', 'ar'):
        arch_names[t['name']] = tid

# For each code used by suffragans, find exact archdiocese match
code_to_archname = {}
for code in code_usage:
    # Exact match
    if code in arch_names:
        code_to_archname[code] = code
        continue
    
    # Try first N letters
    for nlen in range(len(code), 2, -1):
        prefix = code[:nlen]
        for aname in arch_names:
            if aname.startswith(prefix):
                code_to_archname[code] = aname
                break
        if code in code_to_archname:
            break
    
    if code not in code_to_archname:
        # Try removing diacritics
        for aname in arch_names:
            clean_aname = re.sub(r'[^a-z]', '', aname)
            clean_code = re.sub(r'[^a-z]', '', code)
            if clean_aname.startswith(clean_code) or clean_code.startswith(clean_aname[:4]):
                code_to_archname[code] = aname
                break

print(f'{len(code_to_archname)} codes resolved out of {len(code_usage)}')

# Show some mappings
print('\nSample mappings:')
for code in sorted(code_to_archname.keys())[:20]:
    print(f'  {code:10s} -> {code_to_archname[code]}')

# Build hierarchy ID lookups
print('\nBuilding hierarchy lookups...')
arch_name_to_hid = {}
for r in db.execute("""
    SELECT h.id, et.name FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'archdiocese'
"""):
    arch_name_to_hid[r[1].lower()] = r[0]
print(f'{len(arch_name_to_hid)} archdioceses')

dio_hids = {}  # territory_id -> hierarchy_id
for r in db.execute("SELECT id, territory_id FROM catholic_hierarchy WHERE cath_type='diocese' AND territory_id IS NOT NULL"):
    dio_hids[r[1]] = r[0]
print(f'{len(dio_hids)} dioceses')

# Fix links
print('\nFixing suffragan links...')
fixed = 0
for r in db.execute("""
    SELECT h.id, et.id as tid, et.name, et.metro_key
    FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'diocese' AND et.metro_key IS NOT NULL AND et.metro_key != '_met' AND et.metro_key != ''
"""):
    h_id = r[0]
    tid = r[1]
    code = r[3].lower().strip()
    
    arch_name = code_to_archname.get(code)
    if not arch_name:
        continue
    
    arch_hid = arch_name_to_hid.get(arch_name)
    if not arch_hid:
        continue
    
    db.execute("""
        UPDATE catholic_hierarchy 
        SET parent_id=?, parent_cath_type='archdiocese',
            relationship='suffragan_of',
            archdiocese=(SELECT name FROM catholic_hierarchy WHERE id=?)
        WHERE id=?
    """, (arch_hid, arch_hid, h_id))
    fixed += 1
    
    if fixed % 500 == 0:
        db.commit()
        print(f'  {fixed}...')

db.commit()
print(f'{fixed} suffragan links created')

# Verify - check for wrong links
print('\n=== Verification ===')
print('\nSample correct links:')
for r in db.execute("""
    SELECT h1.name, h2.name as arch, h2.cath_type
    FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'suffragan_of' 
      AND h2.cath_type = 'archdiocese'
    LIMIT 15
"""):
    print(f'  {str(r[0])[:40]:40s} -> {str(r[1])[:40]:40s}')

wrong = db.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'suffragan_of' AND h2.cath_type != 'archdiocese'
""").fetchone()[0]
print(f'\nWrong links (child->non-archdiocese): {wrong}')

# Show wrong links
if wrong:
    print('Wrong links:')
    for r in db.execute("""
        SELECT h1.name, h2.name as arch, h2.cath_type
        FROM catholic_hierarchy h1
        JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
        WHERE h1.relationship = 'suffragan_of' AND h2.cath_type != 'archdiocese'
        LIMIT 10
    """):
        print(f'  {str(r[0])[:40]:40s} -> {str(r[1])[:40]:40s} ({r[2]})')

total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE relationship='suffragan_of'").fetchone()[0]
dioceses = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='diocese'").fetchone()[0]
print(f'\nTotal: {total:,} / {dioceses:,} dioceses')

db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_suffragan_v4', '_fix_suffragan5.py', now, now,
     fixed, 'catholic_hierarchy.parent_id,relationship', 'completed',
     f'{fixed} suffragan links'))
db.commit()

print('\nDone!')
db.close()

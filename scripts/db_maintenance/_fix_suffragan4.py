"""Fix suffragan links. Code like 'koln' -> archdiocese name 'Cologne'."""
import sqlite3, re
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

now = datetime.now().isoformat()

# Show actual code patterns
print('=== Metro code patterns vs archdiocese names ===')
for r in db.execute("""
    SELECT et.name, et.metro_key 
    FROM ecclesiastical_territories et
    WHERE et.metro_key IS NOT NULL AND et.metro_key != '_met'
    LIMIT 30
"""):
    print(f'  {str(r[0]):35s} metro={str(r[1] or "-"):10s}')

# Build manual code->archdiocese mapping
# Approach: for each unique metro_key value (excluding '_met'), 
# find the archdiocese whose name matches the code
print('\n=== Building code -> archdiocese name map ===')

# Get all unique metro codes used by suffragan dioceses
suffragan_codes = set()
for r in db.execute("""
    SELECT DISTINCT metro_key FROM ecclesiastical_territories 
    WHERE metro_key IS NOT NULL AND metro_key != '_met' AND metro_key != ''
"""):
    suffragan_codes.add(r[0].lower())
print(f'  {len(suffragan_codes)} unique suffragan codes')

# Get all archdiocese names
archdioceses = {}
for r in db.execute("""
    SELECT et.id, et.name, et.full_name 
    FROM ecclesiastical_territories et
    WHERE et.dio_type IN ('a', 'ar')
"""):
    name = r[1].lower()
    full = r[2].lower()
    archdioceses[r[0]] = {'name': name, 'full': full}
print(f'  {len(archdioceses)} archdioceses')

# Build code -> archdiocese name mapping
code_to_arch = {}
for code in suffragan_codes:
    # Find matching archdiocese
    for aid, info in archdioceses.items():
        # Try various matching strategies
        if (code == info['name'].lower() or 
            code == info['name'].lower()[:len(code)] or
            code in info['name'].lower() or
            info['name'].lower().startswith(code) or
            code == info['full'].lower()[:len(code)] or
            info['full'].lower().startswith(code)):
            code_to_arch[code] = info['name']
            break
    
    if code not in code_to_arch:
        # Try with diacritics removed
        for aid, info in archdioceses.items():
            name_clean = re.sub(r'[^a-z0-9]', '', info['name'].lower())
            code_clean = re.sub(r'[^a-z0-9]', '', code.lower())
            if name_clean.startswith(code_clean) or code_clean.startswith(name_clean[:4]):
                code_to_arch[code] = info['name']
                break

print(f'  {len(code_to_arch)} codes resolved')

# Show unmatched
unmatched = suffragan_codes - set(code_to_arch.keys())
if unmatched:
    print(f'\n  Unmatched codes ({len(unmatched)}):')
    for c in sorted(unmatched)[:20]:
        print(f'    {c}')

# Show matched examples
print('\n  Sample mappings:')
for code in sorted(code_to_arch.keys())[:15]:
    print(f'    {code:10s} -> {code_to_arch[code]}')

# Fix suffragan links
print('\n=== Fixing links ===')

# Build archdiocese name -> hierarchy ID map
arch_name_to_hid = {}
for r in db.execute("""
    SELECT h.id, et.name 
    FROM catholic_hierarchy h 
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'archdiocese'
"""):
    arch_name_to_hid[r[1].lower()] = r[0]
print(f'  {len(arch_name_to_hid)} archdioceses in hierarchy')

# For each diocese with metro_key, find its archdiocese
fixed = 0
for r in db.execute("""
    SELECT h.id, et.name, et.metro_key 
    FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'diocese' AND et.metro_key IS NOT NULL AND et.metro_key != '_met'
"""):
    h_id = r[0]
    code = r[2].lower().strip()
    
    arch_name = code_to_arch.get(code)
    if not arch_name:
        continue
    
    arch_hid = arch_name_to_hid.get(arch_name)
    if not arch_hid:
        continue
    
    db.execute("""
        UPDATE catholic_hierarchy 
        SET parent_id = ?, parent_cath_type = 'archdiocese',
            relationship = 'suffragan_of',
            archdiocese = (SELECT name FROM catholic_hierarchy WHERE id = ?)
        WHERE id = ?
    """, (arch_hid, arch_hid, h_id))
    fixed += 1
    
    if fixed % 500 == 0:
        db.commit()

db.commit()
print(f'  {fixed} suffragan links fixed')

# Verify
print('\n=== Sample links ===')
for r in db.execute("""
    SELECT h1.name, h2.name as arch, h2.cath_type
    FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'suffragan_of'
    LIMIT 15
"""):
    print(f'  {str(r[0])[:40]:40s} -> {str(r[1])[:40]:40s} ({r[2]:12s})')

total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE relationship='suffragan_of'").fetchone()[0]
dioceses = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='diocese'").fetchone()[0]
print(f'\nTotal: {total:,} / {dioceses:,} dioceses ({total*100//dioceses}%)')

# Log
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_suffragan_v3', '_fix_suffragan4.py', now, now,
     fixed, 'catholic_hierarchy.parent_id,relationship', 'completed',
     f'Fixed {fixed} suffragan links'))
db.commit()

print('\nDone!')
db.close()

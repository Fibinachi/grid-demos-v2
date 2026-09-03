"""Fix suffragan links with correct code->name->id chain."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

now = datetime.now().isoformat()

# Step 1: Build code -> territory NAME (not territory id, not wrong)
print('Building code -> name lookup...')
code_to_name = {}  # code like 'koln' -> name like 'cologne'
for r in db.execute("SELECT id, name, metro_key FROM ecclesiastical_territories"):
    if r[2]:
        code_to_name[r[2].lower().strip()] = r[1].lower().strip()
print(f'  {len(code_to_name)} codes mapped')

# Step 2: Build name -> hierarchy id for ARCHDIOCESES only
print('Building archdiocese name lookup...')
arch_name_to_hid = {}
for r in db.execute("""
    SELECT h.id, et.name 
    FROM catholic_hierarchy h 
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'archdiocese'
"""):
    arch_name_to_hid[r[1].lower().strip()] = r[0]
print(f'  {len(arch_name_to_hid)} archdioceses mapped')

# Step 3: Build diocese territory_id -> hierarchy_id map
print('Building diocese territory lookup...')
dio_tid_to_hid = {}
for r in db.execute("""
    SELECT h.id, h.territory_id, et.name, et.metro_key 
    FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type = 'diocese'
"""):
    if r[1]:
        dio_tid_to_hid[r[1]] = {'hid': r[0], 'name': r[2], 'metro_key': r[3]}
print(f'  {len(dio_tid_to_hid)} dioceses mapped')

# Step 4: Fix suffragan links
print('\nFixing suffragan links...')
fixed = 0
no_metro = 0
no_arch = 0

for t_id, info in dio_tid_to_hid.items():
    metro_code = info['metro_key']
    if not metro_code:
        no_metro += 1
        continue
    
    # code -> name -> hierarchy id
    metro_name = code_to_name.get(metro_code.lower().strip())
    if not metro_name:
        no_arch += 1
        continue
    
    arch_hid = arch_name_to_hid.get(metro_name)
    if not arch_hid:
        # Try alternate lookup: maybe the name doesn't match exactly
        for aname, ahid in arch_name_to_hid.items():
            if aname.startswith(metro_name) or metro_name.startswith(aname):
                arch_hid = ahid
                break
    
    if not arch_hid:
        no_arch += 1
        continue
    
    db.execute("""
        UPDATE catholic_hierarchy 
        SET parent_id = ?, parent_cath_type = 'archdiocese',
            relationship = 'suffragan_of',
            archdiocese = (SELECT name FROM catholic_hierarchy WHERE id = ?)
        WHERE id = ?
    """, (arch_hid, arch_hid, info['hid']))
    fixed += 1
    
    if fixed % 500 == 0:
        db.commit()

db.commit()

print(f'\n  Linked: {fixed}')
print(f'  No metro_key: {no_metro}')
print(f'  No archdiocese found: {no_arch}')

# Verify
print('\n=== Sample links ===')
for r in db.execute("""
    SELECT h1.name, h1.cath_type, h2.name as arch, h2.cath_type as arch_type
    FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'suffragan_of'
    LIMIT 15
"""):
    print(f'  {str(r[0])[:40]:40s} ({r[1]:12s}) -> {str(r[2])[:40]:40s} ({r[3]:12s})')

total_linked = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE relationship='suffragan_of'").fetchone()[0]
total_dioceses = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='diocese'").fetchone()[0]
print(f'\nTotal suffragan links: {total_linked:,} / {total_dioceses:,} dioceses ({total_linked*100//total_dioceses}%)')

# Log provenance
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_suffragan_v2', '_fix_suffragan3.py', now, now,
     fixed, 'catholic_hierarchy.parent_id,relationship', 'completed',
     f'Fixed {fixed} suffragan links'))
db.commit()

print('\nDone!')
db.close()

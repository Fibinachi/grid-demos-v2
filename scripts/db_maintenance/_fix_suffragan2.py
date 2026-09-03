"""Fix all suffragan diocese -> archdiocese links using metro_key codes."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

now = datetime.now().isoformat()

# Build lookup: metro_key code -> territory id
print('Building metro_key -> territory_id map...')
code_to_tid = {}  # code -> territory_id
for r in db.execute("SELECT id, name, metro_key FROM ecclesiastical_territories"):
    if r[2]:
        code_to_tid[r[2].lower()] = r[0]
print(f'  {len(code_to_tid)} codes mapped')

# Build lookup: territory id -> hierarchy id
print('Building territory_id -> hierarchy_id map...')
tid_to_hid = {}  # territory_id -> hierarchy_id
for r in db.execute("SELECT id, territory_id, cath_type FROM catholic_hierarchy WHERE territory_id IS NOT NULL"):
    if r[1]:
        tid_to_hid[r[1]] = {'id': r[0], 'type': r[2]}
print(f'  {len(tid_to_hid)} territory IDs mapped to hierarchy')

# Now fix suffragan links using the code-based lookup
print('\nFixing suffragan links...')
eligible = db.execute("""
    SELECT id, name, metro_key, dio_type FROM ecclesiastical_territories 
    WHERE dio_type IN ('d', 'e', 'p', 't', 'm', 'l') AND metro_key IS NOT NULL
""").fetchall()

fixed = 0
skipped = 0
for r in eligible:
    t_id = r[0]
    name = r[1]
    metro_code = r[2].lower()
    dio_type = r[3]
    
    # Look up archdiocese territory by metro code
    metro_tid = code_to_tid.get(metro_code)
    if not metro_tid:
        skipped += 1
        continue
    
    # Get hierarchy IDs
    suff_h = tid_to_hid.get(t_id)
    metro_h = tid_to_hid.get(metro_tid)
    
    if not suff_h or not metro_h:
        skipped += 1
        continue
    
    if metro_h['type'] not in ('archdiocese', 'diocese'):
        skipped += 1
        continue
    
    # Create the link
    db.execute("""
        UPDATE catholic_hierarchy 
        SET parent_id = ?, parent_cath_type = 'archdiocese',
            relationship = 'suffragan_of',
            archdiocese = (SELECT name FROM catholic_hierarchy WHERE id = ?)
        WHERE id = ?
    """, (metro_h['id'], metro_h['id'], suff_h['id']))
    fixed += 1
    
    if fixed % 500 == 0:
        db.commit()
        print(f'    {fixed} linked...')

db.commit()

print(f'\n  Fixed: {fixed}')
print(f'  Skipped (missing lookup): {skipped}')

# Verify
total_linked = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE relationship='suffragan_of'").fetchone()[0]
total_dioceses = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='diocese'").fetchone()[0]
print(f'\nTotal suffragan links: {total_linked:,}')
print(f'Total dioceses: {total_dioceses:,}')
print(f'Coverage: {total_linked*100//total_dioceses}%')

# Sample
print('\nSample links:')
for r in db.execute("""
    SELECT h1.name, h1.cath_type, h2.name as arch
    FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'suffragan_of'
    LIMIT 10
"""):
    print(f'  {str(r[0])[:40]:40s} -> {str(r[2])[:40]:40s}')

# Log provenance
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_suffragan_fix', '_fix_suffragan2.py', now, now,
     fixed, 'catholic_hierarchy.parent_id,relationship', 'completed',
     f'Created {fixed} suffragan diocese->archdiocese links'))
db.commit()

print('\nDone!')
db.close()

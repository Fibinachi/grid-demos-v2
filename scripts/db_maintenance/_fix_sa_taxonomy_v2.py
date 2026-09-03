"""Set proper taxonomy for ALL Salvation Army entries.
Hierarchy: religion_type -> tradition_legacy -> family -> denomination_affiliation
SA = christian -> Protestant -> Holiness Churches -> Salvation Army
"""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

CHUNK = 500

# Get ALL SA entries by name
cur = db.execute("""
    SELECT id, name, religion_type, tradition_legacy, family, subtradition, denomination_affiliation
    FROM churches
    WHERE name LIKE '%Salvation Army%'
       OR name LIKE '%Arm\u00e9e du Salut%'
       OR name LIKE '%Heilsarmee%'
       OR name LIKE '%Frelsesarmeen%'
       OR name LIKE '%Pelastusarmeija%'
       OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
       OR name LIKE '%Ejercito de Salvacion%'
       OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%'
       OR name LIKE '%Exercito de Salvacao%'
       OR name LIKE '%Armia Zbawienia%'
       OR name LIKE '%Fr\u00e4lsningsarm\u00e9n%'
       OR name LIKE '%Fralsningsarmen%'
    ORDER BY id
""")
rows = cur.fetchall()
total = len(rows)
print(f'Total SA entries: {total:,}')

# Current state
print('\nCurrent taxonomy:')
for col in ('religion_type', 'tradition_legacy', 'family', 'subtradition', 'denomination_affiliation'):
    cur2 = db.execute(f"SELECT COALESCE({col},'(NULL)'), COUNT(*) FROM churches WHERE id IN ({','.join('?'*total)}) GROUP BY {col} ORDER BY COUNT(*) DESC", [r[0] for r in rows])
    vals = cur2.fetchall()
    print(f'\n  {col}:')
    for v, c in vals:
        print(f'    {c:>6} | {v}')

# Update ALL SA entries with correct taxonomy:
# religion_type = christian (they are Christian)
# tradition_legacy = Protestant (they are Protestant)
# family = Holiness Churches (they are in the Holiness movement)
# denomination_affiliation = Salvation Army
# Clear subtradition (not a real taxonomy level)
ids = [r[0] for r in rows]
updated = 0
print(f'\nSetting correct taxonomy for all {total} entries...')

for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    placeholders = ','.join('?' * len(batch))
    db.execute(f"""
        UPDATE churches
        SET religion_type = 'christian',
            tradition_legacy = 'Protestant',
            family = 'Holiness Churches',
            denomination_affiliation = 'Salvation Army',
            subtradition = NULL
        WHERE id IN ({placeholders})
    """, batch)
    db.commit()
    updated += len(batch)
    if updated % 1000 == 0 or updated == total:
        print(f'  {updated}/{total} ({updated*100//total}%)')

# Verify
print('\nVerification:')
for col in ('religion_type', 'tradition_legacy', 'family', 'subtradition', 'denomination_affiliation'):
    cur2 = db.execute(f"SELECT COALESCE({col},'(NULL)'), COUNT(*) FROM churches WHERE id IN ({','.join('?'*total)}) GROUP BY {col} ORDER BY COUNT(*) DESC", ids)
    vals = cur2.fetchall()
    print(f'\n  {col}:')
    for v, c in vals:
        print(f'    {c:>6} | {v}')

# Log to provenance_log (per-run table)
now = datetime.now().isoformat()
db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at, 
                                churches_updated, fields_populated, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", ('sa_taxonomy_v2', '_fix_sa_taxonomy_v2.py', now, now,
      total, 'religion_type,tradition_legacy,family,denomination_affiliation', 'completed'))
db.commit()

print(f'\nDone! All {total} SA entries now have consistent taxonomy.')
db.close()

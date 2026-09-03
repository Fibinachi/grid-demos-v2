"""Set proper Christian/Protestant taxonomy for all Salvation Army entries."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

CHUNK = 500

# Get all SA entries by name
cur = db.execute("""
    SELECT id, name, family, tradition_legacy, subtradition, religion_type, denomination_affiliation
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
print('\nCurrent values:')
for col, label in [('family', 'family'), ('tradition_legacy', 'tradition_legacy'), 
                    ('subtradition', 'subtradition'), ('religion_type', 'religion_type')]:
    cur2 = db.execute(f"SELECT {col}, COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(rows))}) GROUP BY {col} ORDER BY COUNT(*) DESC", 
                      [r[0] for r in rows])
    vals = cur2.fetchall()
    print(f'\n  {label}:')
    for v, c in vals:
        print(f'    {c:>6} | {v or "(NULL)"}')

# Update: 
#   family = 'Holiness Churches' (Salvation Army is part of the Holiness movement)
#   tradition_legacy = 'Protestant' (it's a Protestant denomination)
#   subtradition = 'Salvationist' (their own term)
#   religion_type = 'christian' (Christian)
#   denomination_affiliation = 'Salvation Army' (already set)
ids = [r[0] for r in rows]
updated = 0
print(f'\nUpdating {total} entries with Christian/Protestant/Holiness taxonomy...')

for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    placeholders = ','.join('?' * len(batch))
    db.execute(f"""
        UPDATE churches
        SET family = CASE WHEN family IS NULL OR family = '' THEN 'Holiness Churches' ELSE family END,
            tradition_legacy = CASE WHEN tradition_legacy IS NULL OR tradition_legacy = '' THEN 'Protestant' ELSE tradition_legacy END,
            subtradition = CASE WHEN subtradition IS NULL OR subtradition = '' THEN 'Salvationist' ELSE subtradition END,
            religion_type = CASE WHEN religion_type IS NULL OR religion_type = '' THEN 'christian' ELSE religion_type END,
            denomination_affiliation = 'Salvation Army'
        WHERE id IN ({placeholders})
    """, batch)
    db.commit()
    updated += len(batch)
    if updated % 1000 == 0 or updated == total:
        print(f'  {updated}/{total} ({updated*100//total}%)')

# Verify
print('\nVerification:')
for col, label in [('family', 'family'), ('tradition_legacy', 'tradition_legacy'), 
                    ('subtradition', 'subtradition'), ('religion_type', 'religion_type'),
                    ('denomination_affiliation', 'denomination')]:
    cur2 = db.execute(f"SELECT {col}, COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(ids))}) GROUP BY {col} ORDER BY COUNT(*) DESC",
                      ids)
    vals = cur2.fetchall()
    print(f'\n  {label}:')
    for v, c in vals:
        print(f'    {c:>6} | {v or "(NULL)"}')

# Log provenance
print('\nLogging provenance...')
now = datetime.now().isoformat()
prov_batch = []
for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    for cid in batch:
        prov_batch.append((cid, 'sa_taxonomy_fix', 'updated', now, 
                          'Set family=Holiness Churches, tradition_legacy=Protestant, subtradition=Salvationist, religion_type=christian'))
    if len(prov_batch) >= CHUNK:
        db.executemany("""
            INSERT INTO provenance_log (church_id, source, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """, prov_batch)
        db.commit()
        prov_batch = []
if prov_batch:
    db.executemany("""
        INSERT INTO provenance_log (church_id, source, action, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
    """, prov_batch)
    db.commit()
    prov_batch = []

print('Done!')
db.close()

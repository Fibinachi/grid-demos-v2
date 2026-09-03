"""Set denomination_affiliation='Salvation Army' for ALL SA entries."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

CHUNK = 500

# Find ALL SA entries (broad search including denomination field)
cur = db.execute("""
    SELECT id, name, denomination_affiliation
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
print(f'Total SA entries (by name): {total:,}')

# Count current denom states
current_denom = {}
for r in rows:
    d = r[2] or '(NULL)'
    current_denom[d] = current_denom.get(d, 0) + 1

print('\nCurrent denomination_affiliation values:')
for d, c in sorted(current_denom.items(), key=lambda x: -x[1]):
    print(f'  {c:>6} | {d}')

# Update all to "Salvation Army"
print(f'\nSetting all {total} entries to denomination_affiliation = "Salvation Army"...')
ids = [r[0] for r in rows]
updated = 0
for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    placeholders = ','.join('?' * len(batch))
    db.execute(f"""
        UPDATE churches
        SET denomination_affiliation = 'Salvation Army',
            family = CASE WHEN family IS NULL OR family = '' THEN 'Holiness Churches' ELSE family END,
            subtradition = CASE WHEN subtradition IS NULL OR subtradition = '' THEN 'Salvationist' ELSE subtradition END
        WHERE id IN ({placeholders})
    """, batch)
    db.commit()
    updated += len(batch)
    print(f'  {updated}/{total} ({updated*100//total}%)')

# Verify
cur = db.execute("SELECT denomination_affiliation, COUNT(*) FROM churches WHERE id IN ({}) GROUP BY denomination_affiliation ORDER BY COUNT(*) DESC".format(
    ','.join('?' * len(ids))), ids)
print('\nVerification:')
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Also update the sa_hierarchy and provenance
print('\nUpdating sa_hierarchy names (The Salvation Army -> Salvation Army)...')
db.execute("""
    UPDATE sa_hierarchy
    SET name = REPLACE(name, 'The Salvation Army', 'Salvation Army')
    WHERE name LIKE 'The Salvation Army%'
""")
db.commit()
affected = db.execute("SELECT changes()").fetchone()[0]
print(f'  {affected} names updated')

# Log provenance
from datetime import datetime
now = datetime.now().isoformat()
prov_batch = []
for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    for church_id in batch:
        prov_batch.append((church_id, 'sa_denom_fix', 'updated', now, 'denomination_affiliation set to Salvation Army'))
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

print(f'Provenance logged for {len(ids)} entries')
print('\nDone!')
db.close()

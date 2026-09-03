"""Clear denomination field for diocese/archdiocese entries — they're admin units, not denominations."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

# Find all diocese-like entries in denomination
cur = db.execute("""
    SELECT id, denomination, tradition, legacy, faith
    FROM churches
    WHERE (denomination LIKE '%Diocese%'
       OR denomination LIKE '%Archdiocese%'
       OR denomination LIKE '%Eparchy%'
       OR denomination LIKE '%Cathedral%')
      AND denomination IS NOT NULL AND denomination != ''
    ORDER BY denomination
""")
rows = cur.fetchall()
print(f'Total diocese/cathedral entries in denomination: {len(rows)}')

# Show the distinct values
cur2 = db.execute("""
    SELECT denomination, COUNT(*) as cnt
    FROM churches
    WHERE (denomination LIKE '%Diocese%'
       OR denomination LIKE '%Archdiocese%'
       OR denomination LIKE '%Eparchy%'
       OR denomination LIKE '%Cathedral%')
      AND denomination IS NOT NULL AND denomination != ''
    GROUP BY denomination
    ORDER BY cnt DESC
""")
print('\nDistinct values being cleared:')
for r in cur2:
    print(f'  {r[1]:>3} | {r[0][:60]}')

# Clear denomination for these entries (tradition/legacy/faith are already set correctly)
ids = [r[0] for r in rows]
CHUNK = 500
for i in range(0, len(ids), CHUNK):
    batch = ids[i:i + CHUNK]
    placeholders = ','.join('?' * len(batch))
    db.execute(f"""
        UPDATE churches SET denomination = NULL
        WHERE id IN ({placeholders})
    """, batch)
    db.commit()

print(f'\nCleared denomination for {len(ids)} entries')

# Verify no diocese remain in denomination
remaining = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (denomination LIKE '%Diocese%'
       OR denomination LIKE '%Archdiocese%'
       OR denomination LIKE '%Eparchy%'
       OR denomination LIKE '%Cathedral%')
      AND denomination IS NOT NULL AND denomination != ''
""").fetchone()[0]
print(f'Remaining diocese in denomination: {remaining}')

# Log
now = datetime.now().isoformat()
db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ('diocese_denom_fix', '_fix_diocese_denoms.py', now, now,
      len(ids), 'denomination', 'completed',
      'Cleared diocese/archdiocese/cathedral names from denomination field'))
db.commit()

db.close()
print('Done!')

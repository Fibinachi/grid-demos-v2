"""Fix NULL id values on BIC entries — set id = rowid"""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance
db = connect()

with Provenance(db, source="aragon_bic_fix", action="updated",
                fields="id", records_attempted=30) as prov:
    cur = db.execute("UPDATE churches SET id = rowid WHERE id IS NULL AND source LIKE '%Aragón%'")
    prov.churches_updated = cur.rowcount
    db.commit()

print(f"Fixed {prov.churches_updated} entries with NULL id")

# Verify
cur = db.execute("SELECT id, rowid, name FROM churches WHERE source LIKE '%Aragón%'")
rows = cur.fetchall()
for r in rows:
    match = "✓" if r[0] == r[1] else "✗"
    print(f"  id={r[0]} rowid={r[1]} {match} | {r[2][:50]}")

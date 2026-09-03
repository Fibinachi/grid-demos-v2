"""Final SAINTE verification."""
import sqlite3
db = sqlite3.connect(r'E:\grid\churches.db')

cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '% SAINTE %'")
print(f"Total SAINTE in names: {cur.fetchone()[0]}")

# What's left with STE (unexpanded)?
cur = db.execute("""
    SELECT rowid, name FROM churches
    WHERE (name LIKE '% STE %' OR name LIKE '% STE.%')
      AND name NOT LIKE '% SAINTE %'
    ORDER BY rowid
""")
rows = cur.fetchall()
print(f"Remaining unexpanded STE: {len(rows)}")
for r in rows:
    print(f"  rowid={r[0]}: {r[1]}")

# Total Phase 2 remaining
cur = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE ((name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
        OR (name LIKE '% CTR %')
        OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
        OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
        OR (name LIKE '% STE %' OR name LIKE '% STE.%' OR name LIKE '%-STE %'))
""")
print(f"\nPhase 2 candidates remaining: {cur.fetchone()[0]}")

# Total applied
cur = db.execute("SELECT SUM(churches_updated) FROM provenance_log WHERE script_name='_review_batch.py' AND parameters LIKE '%phase2%'")
print(f"Total Phase 2 applied: {cur.fetchone()[0]}")

db.close()

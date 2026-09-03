"""Verify SAINTE expansions and Phase 2 results."""
import sqlite3
db = sqlite3.connect(r'E:\grid\churches.db')

# SAINTE count
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '% SAINTE %'")
print(f"Records with SAINTE in name: {cur.fetchone()[0]}")

# Show some
cur = db.execute("SELECT name FROM churches WHERE name LIKE '% SAINTE %' LIMIT 10")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Remaining STE (should be support orgs or lowercase)
cur = db.execute("""
    SELECT rowid, name FROM churches
    WHERE (name LIKE '% STE %' OR name LIKE '% STE.%')
      AND name NOT LIKE '% SAINTE %'
    LIMIT 25
""")
rows = cur.fetchall()
print(f"\nRemaining unexpanded STE: {len(rows)} shown of {db.execute('SELECT COUNT(*) FROM churches WHERE (name LIKE \"% STE %\" OR name LIKE \"% STE.%\") AND name NOT LIKE \"% SAINTE %\"').fetchone()[0]}")
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
print(f"Total Phase 2 candidates remaining: {cur.fetchone()[0]}")

# Phase 2 total applied from provenance
cur = db.execute("""
    SELECT SUM(churches_updated) FROM provenance_log
    WHERE script_name = '_review_batch.py' AND parameters LIKE '%phase2%'
""")
total = cur.fetchone()[0] or 0
print(f"\nTotal Phase 2 applied (provenance log): {total}")

db.close()

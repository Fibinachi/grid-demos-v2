"""Survey non-church entity types among Phase 2 candidates."""
import sqlite3

DB_PATH = r'E:\grid\churches.db'
db = sqlite3.connect(DB_PATH)

# Phase 2 base conditions (same as _review_batch.py)
phase2_cond = """(
    (name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%')
    OR (name LIKE '% CTR %')
    OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%')
    OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')
)"""

queries = [
    ("TRUST / ESTATE / FOUNDATION / BEQUEST",
     "name LIKE '%TRUST%' OR name LIKE '%ESTATE%' OR name LIKE '%FOUNDATION%' OR name LIKE '%BEQUEST%'"),
    ("BOARD / COUNCIL / COMMITTEE",
     "name LIKE '%BOARD%' OR name LIKE '%COUNCIL%' OR name LIKE '%COMMITTEE%'"),
    ("SOCIETY / ASSEMBLY / CONGREGATION",
     "name LIKE '%SOCIETY%' OR name LIKE '%ASSEMBLY%'"),
    ("WARDEN / CHURCHWARDEN",
     "name LIKE '%WARDEN%'"),
    ("FABRIQUE / PARISH CORP / PAROISSE",
     "name LIKE '%FABRIQUE%' OR name LIKE '%PARISH CORP%' OR name LIKE '%PAROISSE%'"),
    ("MISSION / MINISTRY",
     "name LIKE '%MISSION%' OR name LIKE '%MINISTRY%'"),
]

for label, where in queries:
    c = db.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE ({where}) AND {phase2_cond}
    """)
    count = c.fetchone()[0]
    print(f'{label}: {count:,} candidates')

print()

# Show some TRUST examples
c = db.execute(f"""
    SELECT name FROM churches
    WHERE (name LIKE '%TRUST%' OR name LIKE '%ESTATE%' OR name LIKE '%FOUNDATION%' OR name LIKE '%BEQUEST%')
      AND {phase2_cond}
    ORDER BY id LIMIT 30
""")
rows = c.fetchall()
print('--- TRUST / ESTATE / FOUNDATION (first 30) ---')
for r in rows:
    print(f'  {r[0][:100]}')

print()
# Show some BOARD examples
c = db.execute(f"""
    SELECT name FROM churches
    WHERE (name LIKE '%BOARD%' OR name LIKE '%COUNCIL%' OR name LIKE '%COMMITTEE%')
      AND {phase2_cond}
    ORDER BY id LIMIT 15
""")
rows = c.fetchall()
print('--- BOARD / COUNCIL / COMMITTEE (first 15) ---')
for r in rows:
    print(f'  {r[0][:100]}')

db.close()

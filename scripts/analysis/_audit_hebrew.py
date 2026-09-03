"""Check US Jewish records with HEBREW in the name"""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')
CORE = "faith='Jewish' AND (country='US' OR state IS NOT NULL)"

rows = db.execute(f"""
    SELECT rowid, name, landmark_type, denomination, faith_tradition, city, state
    FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%HEBREW%'
    ORDER BY name
""").fetchall()
print(f'Total US Jewish records with HEBREW in name: {len(rows)}')
print()
for r in rows:
    ft = r[4] or 'NULL'
    denom = (r[3] or 'NULL')[:30]
    print(f'{r[0]:>8}: "{r[1][:70]}"  lm={r[2]:15s}  denom={denom:30s}  ft={ft:20s}  {r[5]}, {r[6]}')

db.close()

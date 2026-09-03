"""Check for Hebrew Christian patterns in US Jewish records"""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')
CORE = "faith='Jewish' AND (country='US' OR state IS NOT NULL)"

# Specifically HEBREW + CHRISTIAN pattern
rows = db.execute(f"""
    SELECT rowid, name, landmark_type, denomination, faith_tradition, city, state
    FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%HEBREW%CHRIST%'
    ORDER BY name
""").fetchall()
print(f'HEBREW + CHRIST: {len(rows)}')
for r in rows:
    ft = r[4] or '?'
    denom = r[3] or '?'
    lm = r[2] or '?'
    print(f'  {r[0]}: "{r[1][:80]}" lm={lm} denom={denom} ft={ft} {r[5]}, {r[6]}')

# HEBREW + CHURCH
rows2 = db.execute(f"""
    SELECT rowid, name, landmark_type, denomination, faith_tradition, city, state
    FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%HEBREW%CHURCH%'
    ORDER BY name
""").fetchall()
print(f'\nHEBREW + CHURCH: {len(rows2)}')
for r in rows2:
    ft = r[4] or '?'
    denom = r[3] or '?'
    lm = r[2] or '?'
    print(f'  {r[0]}: "{r[1][:80]}" lm={lm} denom={denom} ft={ft} {r[5]}, {r[6]}')

# HEBREW but not obviously Jewish keywords
rows3 = db.execute(f"""
    SELECT rowid, name, landmark_type, denomination, faith_tradition, city, state
    FROM churches WHERE {CORE}
    AND UPPER(name) LIKE '%HEBREW%'
    AND UPPER(name) NOT LIKE '%CONGREGATION%'
    AND UPPER(name) NOT LIKE '%SYNAGOGUE%'
    AND UPPER(name) NOT LIKE '%BETH %'
    AND UPPER(name) NOT LIKE '%CHABAD%'
    AND UPPER(name) NOT LIKE '%SCHOOL%'
    AND UPPER(name) NOT LIKE '%ACADEMY%'
    AND UPPER(name) NOT LIKE '%CENTER%'
    AND UPPER(name) NOT LIKE '%INSTITUTE%'
    AND UPPER(name) NOT LIKE '%TEMPLE%'
    AND UPPER(name) NOT LIKE '%ALLIANCE%'
    AND UPPER(name) NOT LIKE '%SOCIETY%'
    AND UPPER(name) NOT LIKE '%LUBAVITCH%'
    AND UPPER(name) NOT LIKE '%ETHIOPIAN%'
    AND UPPER(name) NOT LIKE '%YESHIVA%'
    AND UPPER(name) NOT LIKE '%BENE%'
    AND UPPER(name) NOT LIKE '%EDUCATIONAL%'
    ORDER BY name
""").fetchall()
print(f'\nHEBREW (not obv Jewish): {len(rows3)}')
for r in rows3:
    ft = r[4] or '?'
    denom = r[3] or '?'
    lm = r[2] or '?'
    print(f'  {r[0]}: "{r[1][:80]}" lm={lm} denom={denom} ft={ft} {r[5]}, {r[6]}')

db.close()

import sqlite3

db = sqlite3.connect('churches.db')
cur = db.cursor()

# Broader search: all possible JW name patterns in IRS data
patterns = [
    "JEHOVA",
    "WITNESS",
    "KINGDOM HALL",
    "CONGREGATION OF JEHOVAH",
    "ASSEMBLY HALL",
    "WATCHTOWER"
]

for p in patterns:
    rows = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND source='irs'", (f'%{p}%',)).fetchone()[0]
    print(f'{p:35s}: {rows}')

# How many total IRS records do we have?
total_irs = cur.execute("SELECT COUNT(*) FROM churches WHERE source='irs'").fetchone()[0]
print(f'\nTotal IRS records: {total_irs}')

# How about checking if there are "CONGREGATION" records that might be JW
like_jw = cur.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE source='irs' 
    AND (name LIKE '%CONGREGATION%' OR name LIKE '%CONGREAGATION%')
    AND (name LIKE '%JEHOVAH%' OR name LIKE '%JEHOVAHS%')
""").fetchone()[0]
print(f'IRS congregation records with Jehovah: {like_jw}')

# What about checking in Overture/other sources
rows = cur.execute("SELECT source, COUNT(*) FROM churches WHERE (name LIKE '%JEHOVAH%' AND name LIKE '%WITNESS%') OR name LIKE '%Kingdom Hall%' GROUP BY source").fetchall()
print('\nJW-like records by source:')
for r in rows:
    print(f'  {r[0]:15s}: {r[1]}')

# Let's see if we can identify all IRS records that might be JW congregations
# They file as "[Location] CONGREGATION OF JEHOVAHS WITNESSES" or "ASSEMBLY HALL"
# The IRS has full data - perhaps we got a sample?
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE source='irs' AND (name LIKE '%CONGREGATION%' OR name LIKE '%ASSEMBLY HALL%') AND name LIKE '%JEHOVAH%'").fetchone()[0]
print(f'\nIRS records matching congregation/assembly hall + jehovah pattern: {rows}')

# Check state coverage for the JW-like records
rows = cur.execute("""
    SELECT state, COUNT(*) as cnt 
    FROM churches 
    WHERE source='irs' AND (name LIKE '%JEHOVAH%' AND name LIKE '%WITNESS%')
    GROUP BY state 
    ORDER BY cnt DESC
""").fetchall()
print(f'\nJW IRS records by state ({len(rows)} states):')
for r in rows:
    print(f'  {r[0] or "??":2s}: {r[1]}')

db.close()

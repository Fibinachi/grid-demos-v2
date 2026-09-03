import sqlite3

db = sqlite3.connect('churches.db')
cur = db.cursor()

# Look at the "Witness" records more carefully
rows = cur.execute("SELECT name, city, state, source FROM churches WHERE name LIKE '%Witness%' ORDER BY state, city LIMIT 50").fetchall()
print('=== WITNESS records (first 50) ===')
for r in rows:
    print(f'  {r[0][:60]:60s} {r[1] or "":15s} {r[2] or "":2s} [{r[3] or ""}]')

# Count how many have "JEHOVAH" + "WITNESS" pattern specifically
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE (name LIKE '%JEHOVAH%' AND name LIKE '%WITNESS%') OR name LIKE '%Kingdom Hall%'").fetchone()[0]
print(f'\nLikely actual JW congregations (Jehovah+Witness or Kingdom Hall): {rows}')

# Also search for "CONGREGATION OF JEHOVAH" pattern
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%CONGREGATION%JEHOVAH%'").fetchone()[0]
print(f'  "Congregation...Jehovah..." pattern: {rows}')

# Split the 214 "Jehovah" records into categories
rows = cur.execute("SELECT name FROM churches WHERE name LIKE '%Jehovah%' AND name LIKE '%Witness%'").fetchall()
print(f'\n=== SAMPLE: Jehovah+Witness records ({len(rows)}) ===')
for r in rows[:20]:
    print(f'  {r[0][:70]}')

# Check for just "Jehovah" without "Witness" - likely non-JW churches
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Jehovah%' AND name NOT LIKE '%Witness%'").fetchone()[0]
print(f'\n"Jehovah" without "Witness" (probably other denominations): {rows}')

# Check state distribution of likely JW records
rows = cur.execute("""
    SELECT state, COUNT(*) as cnt 
    FROM churches 
    WHERE (name LIKE '%JEHOVAH%' AND name LIKE '%WITNESS%') OR name LIKE '%Kingdom Hall%'
    GROUP BY state 
    ORDER BY cnt DESC 
    LIMIT 20
""").fetchall()
print('\n=== JW-like records by state ===')
for r in rows:
    print(f'  {r[0] or "??":2s}: {r[1]}')

db.close()

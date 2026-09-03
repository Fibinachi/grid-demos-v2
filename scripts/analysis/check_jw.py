import sqlite3

db = sqlite3.connect('churches.db')
cur = db.cursor()

# Search for Kingdom Halls, Jehovah's Witnesses, Watchtower
patterns = ['Kingdom Hall', 'Jehovah', 'Watchtower', 'Witness']
for p in patterns:
    rows = cur.execute('SELECT COUNT(*) FROM churches WHERE name LIKE ?', (f'%{p}%',)).fetchone()[0]
    websites = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND website IS NOT NULL AND website != ''", (f'%{p}%',)).fetchone()[0]
    print(f'{p:20s}: {rows:>6} total, {websites:>4} with websites')

print()

# Show some samples
rows = cur.execute('SELECT name, city, state, website FROM churches WHERE name LIKE "%Kingdom Hall%" LIMIT 20').fetchall()
print(f'Sample Kingdom Halls ({len(rows)} shown):')
for r in rows:
    city = r[1] or ''
    state = r[2] or ''
    web = r[3] or ''
    print(f'  {r[0][:45]:45s} {city[:15]:15s} {state:2s}  {web[:30]:30s}')

print()

# Also check denomination field
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE denomination LIKE '%jehovah%' OR denomination LIKE '%witness%' OR denomination LIKE '%watchtower%'").fetchone()[0]
print(f'Tagged as JW in denomination field: {rows}')

rows = cur.execute("SELECT DISTINCT denomination FROM churches WHERE denomination LIKE '%jehovah%' OR denomination LIKE '%witness%' OR denomination LIKE '%kingdom hall%'").fetchall()
for r in rows:
    print(f'  Denom: {r[0]}')

# Also check IRS data source for Kingdom Halls
rows = cur.execute("SELECT source, COUNT(*) FROM churches WHERE name LIKE '%Kingdom Hall%' GROUP BY source").fetchall()
print()
print('By source:')
for r in rows:
    print(f'  {r[0]:30s}: {r[1]}')

db.close()

"""Audit suspicious country Jewish entries for misclassifications."""
import sqlite3

c = sqlite3.connect(r'E:\grid\churches.db')

countries = [
    ('SA', 'Saudi Arabia'),
    ('TH', 'Thailand'),
    ('JO', 'Jordan'),
    ('TR', 'Turkey'),
    ('PS', 'Palestine'),
    ('IL', 'Israel'),
    ('JO', 'Jordan'),
    ('SA', 'Saudi Arabia'),
]

for country, label in countries:
    cnt = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country=?", (country,)).fetchone()[0]
    print(f'=== {country} ({label}) — {cnt:,} records ===')
    
    rows = c.execute("SELECT name, source, landmark_type, faith_tradition FROM churches WHERE faith='Jewish' AND country=? ORDER BY RANDOM() LIMIT 15", (country,)).fetchall()
    for r in rows:
        print(f'  name=%-55s source=%-30s type=%-15s tradition=%s' % (r[0][:55] if r[0] else '', r[1][:30] if r[1] else '', r[2] or '', r[3] or ''))
    
    lt = c.execute("SELECT landmark_type, COUNT(*) as cnt FROM churches WHERE faith='Jewish' AND country=? AND landmark_type IS NOT NULL AND landmark_type != '' GROUP BY landmark_type ORDER BY cnt DESC", (country,)).fetchall()
    if lt:
        print('  Landmark types:')
        for r2 in lt:
            print(f'    {r2[0]}: {r2[1]:,}')
    
    ft = c.execute("SELECT faith_tradition, COUNT(*) as cnt FROM churches WHERE faith='Jewish' AND country=? AND faith_tradition IS NOT NULL AND faith_tradition != '' GROUP BY faith_tradition ORDER BY cnt DESC", (country,)).fetchall()
    if ft:
        print('  Faith traditions:')
        for r2 in ft:
            print(f'    {r2[0]}: {r2[1]:,}')
    print()

# Also check what's driving the high counts in specific countries
print('=== Countries with 100+ Jewish entries (sorted) ===')
rows = c.execute("""
    SELECT country, COUNT(*) as cnt 
    FROM churches 
    WHERE faith='Jewish' AND country IS NOT NULL AND country != ''
    GROUP BY country 
    HAVING cnt >= 100 
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f'  {r[0]:4s}: {r[1]:>6,}')

# Check the Saudi 1,197 specifically - what source?
print()
print('=== Saudi Jewish — source breakdown ===')
rows = c.execute("SELECT source, COUNT(*) as cnt FROM churches WHERE faith='Jewish' AND country='SA' GROUP BY source ORDER BY cnt DESC").fetchall()
for r in rows:
    print(f'  {r[0]:40s}: {r[1]:>6,}')

c.close()

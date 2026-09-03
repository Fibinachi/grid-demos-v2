"""
Search for archaeological/ancient sites that may be misclassified by faith.
Look for name patterns suggesting ancient/archaeological sites.
"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Archaeological / ancient-site name keywords
keywords = [
    'acropolis', 'forum', 'necropolis', 'amphitheatre', 'amphitheater',
    'colosseum', 'circus maximus', 'catacomb', 'hypogeum', 'aqueduct',
    'porta', 'thermae', 'odeon', 'arch of', 'temple of', 'temple d',
    'temple de', 'temple romano', 'temple greco', 'temple antique',
    'antico tempio', 'pyramid', 'sphinx', 'obelisk', 'baths of',
    'dolmen', 'megalith', 'stonehenge', 'standing stone', 'menhir',
    'cromlech', 'henge', 'mausoleum', 'pantheon', 'parthenon',
    'colosseo', 'coliseum', 'circo', 'teatro greco', 'teatro romano',
    'ruins', 'ruine', 'rovin', 'ancient', 'archeological', 'archaeological',
    'tempio', 'templo',
]

conditions = [f"name LIKE '%{kw}%' COLLATE NOCASE" for kw in keywords]
all_conditions = ' OR '.join(conditions)

# --- Part 1: Non-Christian entries ---
query1 = f'''
SELECT id, name, faith, faith_tradition, country, city, latitude, longitude, source
FROM churches
WHERE ({all_conditions})
  AND faith IS NOT NULL
  AND faith NOT IN ('Christian', 'Buddhist', 'Hindu')
ORDER BY faith, country
'''
c.execute(query1)
rows1 = c.fetchall()
print(f"=== Archaeological-sounding sites with NON-Christian/non-Hindu/non-Buddhist faith ===")
print(f"Found {len(rows1)} entries")
print()
for r in rows1:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | trait={str(r[3] or '-'):15s} | {str(r[1] or '')[:75]:75s} | {r[4] or '-'}")

print()
print("=" * 100)

# --- Part 2: Entries tagged as Hindu that are likely ancient ---
query2 = f'''
SELECT id, name, faith, faith_tradition, country, city, latitude, longitude, source
FROM churches
WHERE ({all_conditions})
  AND faith = 'Hindu'
ORDER BY country, name
'''
c.execute(query2)
rows2 = c.fetchall()
print(f"\n=== Archaeological-sounding sites tagged as HINDU ===")
print(f"Found {len(rows2)} entries")
print()
for r in rows2:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | {str(r[1] or '')[:75]:75s} | {str(r[4] or '-'):15s} | {str(r[5] or '-'):20s} | {r[8] or '-'}")

print()
print("=" * 100)

# --- Part 3: Also check for entries tagged with generic "Other" or similar ---
query3 = f'''
SELECT id, name, faith, faith_tradition, country, city, latitude, longitude, source
FROM churches
WHERE ({all_conditions})
  AND faith IN ('Other', 'Pagan', 'Animist')
ORDER BY faith, country
'''
c.execute(query3)
rows3 = c.fetchall()
print(f"\n=== Archaeological-sounding sites with faith=Other/Pagan/Animist ===")
print(f"Found {len(rows3)} entries")
print()
for r in rows3:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | trait={str(r[3] or '-'):15s} | {str(r[1] or '')[:75]:75s} | {r[4] or '-'}")

conn.close()

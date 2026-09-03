"""
Focused search for actual archaeological/ancient sites misclassified by faith.
Excludes the US (where "Temple of..." are mostly churches) and focuses on
identifiable ancient/archaeological structures.
"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Archaeological keywords that strongly suggest an ancient/non-religious site
arch_keywords = [
    # Ancient ruins
    "ruins", "ruine", "ruin", "rovine",
    "acropolis", "forum romanum", "necropolis",
    "amphitheatre", "amphitheater", "colosseum",
    "catacomb", "hypogeum", "aqueduct",
    "odeon", "odeum", "thermae",
    # Specific known structures
    "pantheon", "parthenon", "colosseo", "coliseum",
    "circus maximus", "flavian",
    # Masonic (not religious)
    "masonic temple", "masonic lodge",
    # Ancient deities in name
    "temple of diana", "temple of isis", "temple of pan",
    "temple of set", "temple of apollo", "temple of zeus",
    "temple of athena", "temple of artemis", "temple of poseidon",
    "temple of jupiter", "temple of juno", "temple of mars",
    "temple of venus", "temple of minerva", "temple of saturn",
    "temple of hercules", "temple of bacchus",
    "temple of hera", "temple of demeter", "temple of hades",
    "temple of hephaestus", "temple of dionysus",
    "temple of sol", "temple of mithra",
    "tempio di", "templo de",
    # Ancient site markers
    "old sheldon",
    # Also check for specific ancient structures
    # Ancient site markers
    "old sheldon",
    "porta maggiore", "porta nigra",
    "mausoleum",
]

conditions = [f"name LIKE '%{kw}%' COLLATE NOCASE" for kw in arch_keywords]
all_conditions = ' OR '.join(conditions)

# Search with country filter — exclude US (mostly churches with "temple" in name)
query = f'''
SELECT id, name, faith, faith_tradition, country, city, latitude, longitude, source
FROM churches
WHERE ({all_conditions})
  AND faith IS NOT NULL
  AND (country IS NULL OR country != 'US' OR name LIKE '%ruin%' OR name LIKE '%masonic%')
ORDER BY faith, country, name
'''

c.execute(query)
rows = c.fetchall()
print(f"=== Archaeological/ancient sites with potential faith issues (non-US) ===")
print(f"Found {len(rows)} entries")
print()
for r in rows:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | trait={str(r[3] or '-'):15s} | {str(r[1] or '')[:80]:80s} | {r[4] or '-'} | {str(r[5] or '-'):20s}")

print()
print("=" * 100)

# Also check ALL entries with "ruins" or "ruine" regardless of country
query2 = f'''
SELECT id, name, faith, faith_tradition, country, city, latitude, longitude, source
FROM churches
WHERE (name LIKE '%ruin%' OR name LIKE '%ruine%' OR name LIKE '%rovine%')
  AND faith IS NOT NULL
ORDER BY faith, country
'''
c.execute(query2)
rows2 = c.fetchall()
print(f"\n=== ALL entries with 'ruin' in name ===")
print(f"Found {len(rows2)} entries")
print()
for r in rows2:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | {str(r[1] or '')[:80]:80s} | {r[4] or '-'} | {str(r[5] or '-'):20s} | src={r[8] or '-'}")

print()
print("=" * 100)

# Also check Pagan/Other faith entries — see what's there
query3 = f'''
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE faith IN ('Pagan', 'Animist', 'Other')
ORDER BY country, name
'''
c.execute(query3)
rows3 = c.fetchall()
print(f"\n=== Entries with faith=Pagan/Animist/Other ===")
print(f"Found {len(rows3)} entries")
print()
for r in rows3:
    rid = str(r[0] or '-')
    print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | trait={str(r[3] or '-'):20s} | {str(r[1] or '')[:80]:80s} | {r[4] or '-'} | {str(r[5] or '-'):20s}")

conn.close()

"""Quick check for ruins and ancient sites needing faith fixes."""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

S7 = "{r[6] or '-'}"

def print_row(r, has_trait=False):
    """Print a result row. r = (id, name, faith, faith_tradition, country, city, source)"""
    rid = str(r[0] or '-')
    src = str(r[6] or '-')
    if has_trait:
        print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | trait={str(r[3] or '-'):15s} | {str(r[1] or '')[:85]:85s} | {r[4] or '-'} | {str(r[5] or '-'):20s} | src={src}")
    else:
        print(f"{rid:>8} | faith={str(r[2] or '-'):12s} | {str(r[1] or '')[:85]:85s} | {r[4] or '-'} | {str(r[5] or '-'):20s} | src={src}")

# --- 1. ALL entries with 'ruin' in name ---
print("=== ALL entries with 'ruin' in name ===")
c.execute("""
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE name LIKE '%ruin%' OR name LIKE '%ruine%' OR name LIKE '%rovine%'
ORDER BY faith, country
""")
rows = c.fetchall()
print(f"Found {len(rows)} entries\n")

non_christian = [r for r in rows if r[2] != 'Christian']
print(f"--- Non-Christian ruins ({len(non_christian)}) ---")
for r in non_christian:
    print_row(r)
print()
christian = [r for r in rows if r[2] == 'Christian']
print(f"Christian ruins: {len(christian)} entries (mostly correct)\n")

# --- 2. Ancient deity temples ---
print("=" * 120)
print("=== 'Temple of [ancient deity]' entries ===")
ancient_deities = [
    "temple of diana", "temple of isis", "temple of pan",
    "temple of set", "temple of apollo", "temple of zeus",
    "temple of athena", "temple of artemis", "temple of poseidon",
    "temple of jupiter", "temple of juno", "temple of mars",
    "temple of venus", "temple of saturn", "temple of hercules",
    "temple of bacchus", "temple of demeter", "temple of hades",
    "temple of hephaestus", "temple of dionysus",
    "temple of sol", "temple of mithra",
    "temple of minerva", "temple of ceres", "temple of vesta",
    "temple of janus", "temple of mercury", "temple of neptune",
]
conditions = " OR ".join([f"name LIKE '%{d}%'" for d in ancient_deities])
c.execute(f"""
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE ({conditions}) AND faith IS NOT NULL AND faith != 'Christian'
ORDER BY country, name
""")
rows = c.fetchall()
print(f"Found {len(rows)} entries\n")
for r in rows:
    print_row(r, has_trait=True)
print()

# --- 3. Masonic entries not yet tagged ---
print("=" * 120)
print("=== Masonic entries NOT yet Other/Masonic ===")
c.execute("""
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE name LIKE '%masonic%'
  AND (faith IS NULL OR faith != 'Other' OR faith_tradition IS NULL OR faith_tradition != 'Masonic')
ORDER BY country
""")
rows = c.fetchall()
print(f"Found {len(rows)} entries\n")
for r in rows:
    print_row(r, has_trait=True)
print()

# --- 4. Pagan entries ---
print("=" * 120)
print("=== Pagan entries ===")
c.execute("""
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE faith = 'Pagan'
ORDER BY country, name
""")
rows = c.fetchall()
print(f"Found {len(rows)} entries\n")
for r in rows:
    print_row(r, has_trait=True)
print()

# --- 5. Catacomb entries ---
print("=" * 120)
print("=== Catacomb entries (non-Christian) ===")
c.execute("""
SELECT id, name, faith, faith_tradition, country, city, source
FROM churches
WHERE name LIKE '%catacomb%' AND (faith IS NULL OR faith != 'Christian')
ORDER BY country
""")
rows = c.fetchall()
print(f"Found {len(rows)} entries\n")
for r in rows:
    print_row(r, has_trait=True)

conn.close()

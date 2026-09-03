import sqlite3

# Read checkpoint
with open('_osm_checkpoint.txt') as f:
    done = set(line.strip() for line in f if line.strip())

# Read world borders
conn = sqlite3.connect('data/natural_earth/world_borders.db')
c = conn.cursor()
c.execute("SELECT iso_a2, name FROM world_borders WHERE iso_a2 IS NOT NULL AND iso_a2 != '-99' ORDER BY iso_a2")
all_countries = {r[0]: r[1] for r in c.fetchall()}
conn.close()

# Find remaining
remaining = {iso: name for iso, name in all_countries.items() if iso not in done}

print(f"China (CN) in done: {'CN' in done}")
print(f"Countries done: {len(done)}")
print(f"Countries in world_borders (non -99): {len(all_countries)}")
print(f"Remaining: {len(remaining)}")
print()

for iso, name in sorted(remaining.items()):
    print(f"  {iso} {name}")

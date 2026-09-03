import sqlite3, math

conn = sqlite3.connect('churches.db')
conn.execute("PRAGMA journal_mode=DELETE")
conn.execute("PRAGMA synchronous=OFF")

# 1. Find counties with zero churches
print("=== COUNTIES WITH ZERO CHURCHES ===\n")

# Get county_fips_lookup schema
cols = [r[1] for r in conn.execute("PRAGMA table_info(county_fips_lookup)")]
print(f"county_fips_lookup columns: {cols}")

# Get sample
print("\nSample rows from county_fips_lookup:")
for r in conn.execute("SELECT * FROM county_fips_lookup LIMIT 3"):
    print(f"  {r}")

# Count which counties have churches
church_counties = set()
for r in conn.execute("SELECT DISTINCT county_fips FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''"):
    church_counties.add(r[0])

# All counties from lookup
all_counties = {}
for r in conn.execute("SELECT * FROM county_fips_lookup"):
    fips = r[0]
    all_counties[fips] = r

# Church-free counties
no_church = [(fips, all_counties[fips]) for fips in all_counties if fips not in church_counties]
print(f"\nTotal counties in lookup: {len(all_counties):,}")
print(f"Counties with churches: {len(church_counties):,}")
print(f"Counties with ZERO churches: {len(no_church):,}")

# Show church-free counties with demographics
print(f"\n{'FIPS':6s} {'County Name':35s} {'State':5s} {'Population':>12s}")
print("-" * 65)
for fips, row in sorted(no_church, key=lambda x: (x[1][1] if len(x[1])>1 else '', x[1][2] if len(x[1])>2 else '')):
    name = row[1] if len(row) > 1 else '?'
    state = row[2] if len(row) > 2 else '?'
    pop = row[3] if len(row) > 3 else 0
    print(f"{fips:6s} {name:35s} {state:5s} {pop:>12,}")

conn.close()

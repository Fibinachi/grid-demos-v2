"""Per-country valuation stat block for GRID."""
import sqlite3

db = sqlite3.connect('churches.db')
c = db.cursor()

print("=== PER-COUNTRY CORE STATS ===")
print(f"{'country':20s} {'total':>8s} {'geocoded':>8s} {'%geo':>6s} {'%addr':>6s} {'%city':>6s} {'%state':>6s}")

c.execute("""
SELECT 
    COALESCE(country, 'NULL'),
    COUNT(*),
    SUM(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 ELSE 0 END),
    SUM(CASE WHEN address IS NOT NULL AND address != '' AND address != 'None' THEN 1 ELSE 0 END),
    SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END),
    SUM(CASE WHEN state IS NOT NULL AND state != '' THEN 1 ELSE 0 END)
FROM churches 
GROUP BY country 
ORDER BY COUNT(*) DESC 
LIMIT 30
""")
for r in c.fetchall():
    t = r[1]
    print(f"{r[0]:20s} {t:>8,} {r[2]:>8,} {100*r[2]/t:>5.1f}% {100*r[3]/t:>5.1f}% {100*r[4]/t:>5.1f}% {100*r[5]/t:>5.1f}%")

# Grand total
c.execute("SELECT COUNT(*), SUM(CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END) FROM churches")
t, g = c.fetchone()
print(f"\n{'TOTAL':20s} {t:>8,} {g:>8,} {100*g/t:>5.1f}%")
print()

# Census unit coverage - check what church_census_* tables exist
print("=== CENSUS/ELECTION ENRICHMENT TABLES ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'church_census_%' OR name LIKE 'church_election_%' OR name LIKE 'census_%') ORDER BY name")
tables = [r[0] for r in c.fetchall()]
for tbl in tables:
    c.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = c.fetchone()[0]
    print(f"  {tbl:40s} {cnt:>10,}")

print()

# Census unit coverage per country
print("=== CENSUS UNIT ASSIGNMENT (% of churches with census link) ===")
for tbl in tables:
    iso = tbl.split('_')[-1] if '_' in tbl else ''
    if len(iso) == 2:
        c.execute(f"""
            SELECT COUNT(DISTINCT c.id) FROM churches c 
            JOIN {tbl} x ON c.id = x.church_id 
            WHERE c.country IN (SELECT country_name FROM country_codes WHERE iso2='{iso}')
               OR c.country LIKE (SELECT country_name FROM country_codes WHERE iso2='{iso}') || '%'
        """)
        linked = c.fetchone()[0]
        c.execute(f"SELECT COUNT(*) FROM churches WHERE country IN (SELECT country_name FROM country_codes WHERE iso2='{iso}')")
        total_co = c.fetchone()[0]
        if total_co > 0:
            print(f"  {iso} {tbl:38s} {linked:>10,} / {total_co:>10,} ({100*linked/total_co:.1f}%)")

print()

# Schema: key columns
print("=== KEY SCHEMA FIELDS ===")
c.execute("PRAGMA table_info(churches)")
cols = c.fetchall()
key_cols = ['id', 'name', 'address', 'city', 'state', 'zip', 'country', 'county',
            'latitude', 'longitude', 'faith', 'tradition', 'denomination',
            'landmark_type', 'taxonomy_id', 'confidence_score',
            'county_fips_5']
for col in cols:
    if col[1] in key_cols:
        print(f"  churches.{col[1]:25s} {col[2]:15s}")

# Check RUCC
c.execute("SELECT COUNT(*) FROM rucc_codes")
print(f"\n  rucc_codes (urban/rural): {c.fetchone()[0]:,} rows")

# Temporal: boundary vintages
print("\n=== BOUNDARY VINTAGE METADATA ===")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%vintage%' OR name LIKE '%boundary%' OR name LIKE '%version%'")
vintage_tables = c.fetchall()
if vintage_tables:
    for vt in vintage_tables:
        print(f"  {vt[0]}")
else:
    print("  (no vintage metadata tables found)")

# Check church_census_catalog for vintage info
c.execute("SELECT * FROM church_census_catalog LIMIT 5")
cat_rows = c.fetchall()
if cat_rows:
    print("\n=== church_census_catalog (first 5) ===")
    c.execute("PRAGMA table_info(church_census_catalog)")
    cat_cols = [r[1] for r in c.fetchall()]
    print(f"  Columns: {', '.join(cat_cols)}")
    for row in cat_rows:
        print(f"  {dict(zip(cat_cols, row))}")

# Capacity / size fields
print("\n=== CAPACITY / SIZE FIELDS ===")
c.execute("PRAGMA table_info(churches)")
has_capacity = False
for col in cols:
    if any(k in col[1].lower() for k in ['capacity', 'size', 'attendance', 'members', 'adherent', 'seats']):
        print(f"  churches.{col[1]:25s} {col[2]:15s}")
        has_capacity = True
if not has_capacity:
    print("  (no capacity/size columns in churches)")

# Check ARDA for adherents
c.execute("SELECT COUNT(*) FROM arda_counts")
arda = c.fetchone()[0]
print(f"\n  arda_counts (adherents by county/denom): {arda:,} rows")

db.close()

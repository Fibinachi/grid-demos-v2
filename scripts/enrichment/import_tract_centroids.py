"""
Step 1: Download Census tract centroids and store in tract_centroids_us
Uses Census Bureau 2023 Gazetteer — tract-level INTPTLAT/INTPTLON
"""
import sqlite3, requests, io, csv, gzip

db = sqlite3.connect('churches.db')

# Census 2023 Tract Gazetteer
URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_tracts_national.zip"
# Fallback: try the txt version
URL_FALLBACK = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_tracts_national.txt"

print(f"Downloading tract gazetteer...")
try:
    resp = requests.get(URL, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")
    
    import zipfile, io as io_module
    with zipfile.ZipFile(io_module.BytesIO(resp.content)) as z:
        fname = z.namelist()[0]
        print(f"  Extracting: {fname}")
        content = z.read(fname).decode('latin-1')
except Exception as e:
    print(f"  ZIP failed ({e}), trying TXT...")
    resp = requests.get(URL_FALLBACK, timeout=60)
    content = resp.text

# Parse tab-separated file
# Columns: GEOID, ... INTPTLAT, INTPTLON
reader = csv.DictReader(io.StringIO(content), delimiter='\t')
rows = list(reader)
print(f"  Parsed {len(rows):,} tract rows")

# Get column names
cols = list(rows[0].keys())
print(f"  Columns: {cols}")

# Find the right columns (census is inconsistent with naming)
lat_col = next((c for c in cols if 'LAT' in c.upper() and 'INT' in c.upper()), None)
lon_col = next((c for c in cols if 'LON' in c.upper() and 'INT' in c.upper()), None)
geoid_col = next((c for c in cols if 'GEOID' in c.upper()), None)

print(f"  GEOID col: {geoid_col}, LAT col: {lat_col}, LON col: {lon_col}")

if not all([lat_col, lon_col, geoid_col]):
    print("  Could not find required columns. Trying alternative names...")
    # Print first row to debug
    print(f"  First row: {rows[0]}")
    db.close()
    exit(1)

# Create table
db.execute("DROP TABLE IF EXISTS tract_centroids_us")
db.execute("""
    CREATE TABLE tract_centroids_us (
        tract_fips TEXT PRIMARY KEY,
        intpt_lat REAL NOT NULL,
        intpt_lon REAL NOT NULL,
        land_area_sqmi REAL,
        water_area_sqmi REAL
    )
""")

# Insert only tracts that exist in our FEMA data
fema_tracts = set(r[0] for r in db.execute("SELECT DISTINCT TRACTFIPS FROM fema_nri_tract"))

inserted = 0
skipped = 0
for row in rows:
    geoid = row[geoid_col].strip()
    if geoid not in fema_tracts:
        skipped += 1
        continue
    
    try:
        lat = float(row[lat_col])
        lon = float(row[lon_col])
        land = float(row.get('ALAND', row.get('ALAND_SQMI', 0)))
        water = float(row.get('AWATER', row.get('AWATER_SQMI', 0)))
        
        db.execute("""
            INSERT OR IGNORE INTO tract_centroids_us (tract_fips, intpt_lat, intpt_lon, land_area_sqmi, water_area_sqmi)
            VALUES (?, ?, ?, ?, ?)
        """, (geoid, lat, lon, land, water))
        inserted += 1
    except (ValueError, KeyError):
        continue

db.commit()

# Verify
total = db.execute("SELECT COUNT(*) FROM tract_centroids_us").fetchone()[0]
with_elevation = total
print(f"\n  Inserted: {inserted:,} tracts (skipped {skipped:,} non-FEMA tracts)")
print(f"  Total in tract_centroids_us: {total:,}")

# Sample
print("\n  Sample centroids:")
for r in db.execute("SELECT * FROM tract_centroids_us LIMIT 5"):
    print(f"    {r[0]}: ({r[1]:.6f}, {r[2]:.6f})")

db.close()
print("\nDone. tract_centroids_us table created.")

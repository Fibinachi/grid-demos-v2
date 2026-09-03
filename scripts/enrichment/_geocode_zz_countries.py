"""
Use point-in-polygon spatial join with Natural Earth country boundaries
to assign country codes for 12,028 records with country='ZZ' but valid coords.
"""
import sqlite3
import geopandas as gpd
import pandas as pd
import datetime
from pathlib import Path

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
DATA_DIR = Path('data/shapefiles')

# ── Load world boundaries (50m for small islands) ──────────────────────────
world_path = DATA_DIR / 'ne_50m_admin_0_countries.shp'
world_url = 'https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip'

if not world_path.exists():
    print(f"Downloading 50m world boundaries...")
    import urllib.request, zipfile, io
    resp = urllib.request.urlopen(world_url)
    with zipfile.ZipFile(io.BytesIO(resp.read())) as zf:
        zf.extractall(DATA_DIR)
    print("Downloaded.")

world = gpd.read_file(world_path)
world = world[['ISO_A2', 'NAME', 'geometry']].copy()
world = world[world['ISO_A2'] != '-99']  # Remove "unclassified"
print(f"  {len(world)} countries loaded")

# ── Load ZZ records with coords ─────────────────────────────────────────────
conn = sqlite3.connect(DB, timeout=30)
df = pd.read_sql_query("""
    SELECT id, name, latitude, longitude, country, source
    FROM churches WHERE country='ZZ' AND latitude IS NOT NULL
""", conn)

print(f"ZZ records with coords: {len(df):,}")

# ── Create GeoDataFrame with id as index ────────────────────────────────────
df = df.set_index('id')
gdf = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs='EPSG:4326'
)

print("Running spatial join (point-in-polygon)...")
joined = gpd.sjoin(gdf, world, how='left', predicate='intersects')
# Keep only first match per id (border cases)
joined = joined[~joined.index.duplicated(keep='first')]
print(f"  Matched: {joined['ISO_A2'].notna().sum():,}")
print(f"  Unmatched: {joined['ISO_A2'].isna().sum():,}")

# ── Show sample matches ──────────────────────────────────────────────────────
print("\nSample matches:")
matched_df = joined[joined['ISO_A2'].notna()]
for idx, row in matched_df.head(15).iterrows():
    name = str(row['name'] or '')[:50]
    print(f"  {name:<50} ({row['latitude']:.2f}, {row['longitude']:.2f}) → {row['ISO_A2']} ({row['NAME']})")

# ── Show unmatched ──────────────────────────────────────────────────────────
unmatched_df = joined[joined['ISO_A2'].isna()]
if len(unmatched_df) > 0:
    print(f"\nUnmatched ({len(unmatched_df)}):")
    for _, row in unmatched_df.head(10).iterrows():
        name = str(row['name'] or '')[:50]
        print(f"  {name:<50} ({row['latitude']:.4f}, {row['longitude']:.4f})")

# ── Update database (BATCH: single UPDATE with temp table) ─────────────────
# Create temp mapping table
c = conn.cursor()
c.execute("CREATE TEMP TABLE IF NOT EXISTS _zz_country_map (id INTEGER PRIMARY KEY, country TEXT)")
c.execute("DELETE FROM _zz_country_map")

# Batch insert the mapping (id is the GeoDataFrame index)
batch_size = 1000
rows = []
for idx, row in matched_df.iterrows():
    rows.append((int(idx), str(row['ISO_A2'])))

for i in range(0, len(rows), batch_size):
    c.executemany("INSERT OR REPLACE INTO _zz_country_map VALUES (?, ?)", rows[i:i+batch_size])

print(f"Mapping table: {len(rows)} rows inserted")

# Single UPDATE with JOIN
c.execute("""
    UPDATE churches SET country = (SELECT country FROM _zz_country_map WHERE id = churches.id)
    WHERE id IN (SELECT id FROM _zz_country_map)
""")
updated = c.rowcount

conn.commit()
print(f"\nDatabase updated: {updated} records")

# ── Log ─────────────────────────────────────────────────────────────────────
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_geocode_zz_countries.py', TS, TS,
      updated, 0, 'country', 'completed',
      f'Geocoded {updated} ZZ records to country via point-in-polygon (Natural Earth 110m)'))

conn.commit()

# ── Summary ─────────────────────────────────────────────────────────────────
print("\n=== Final ZZ count ===")
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
print(f"  Remaining ZZ: {c.fetchone()[0]:,}")

conn.close()
print("Done!")

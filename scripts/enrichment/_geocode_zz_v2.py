"""
Simplified ZZ country geocoding using spatial join + manual ID tracking.
"""
import sqlite3, geopandas as gpd, pandas as pd, datetime
from pathlib import Path

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
DATA_DIR = Path('data/shapefiles')

# Load world (50m for small islands)
world_path = DATA_DIR / 'ne_50m_admin_0_countries.shp'
world = gpd.read_file(world_path)
world = world[['ISO_A2', 'NAME', 'geometry']].copy()
world = world[world['ISO_A2'] != '-99']
print(f"Countries: {len(world)}")

# Load ZZ records
conn = sqlite3.connect(DB, timeout=30)
df = pd.read_sql_query("""
    SELECT id, name, latitude, longitude FROM churches
    WHERE country='ZZ' AND latitude IS NOT NULL
""", conn)
print(f"ZZ records: {len(df):,}")

# Create geo points
gdf = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs='EPSG:4326'
)

# Spatial join - left join to keep all
joined = gpd.sjoin(gdf, world, how='left', predicate='within')
print(f"Joined rows: {len(joined)}")
print(f"Matched: {joined['ISO_A2'].notna().sum():,}")
print(f"Unmatched: {joined['ISO_A2'].isna().sum():,}")

# Deduplicate by original id (keep first match per id)
matched = joined[joined['ISO_A2'].notna()].copy()
matched = matched.drop_duplicates(subset='id', keep='first')
print(f"Unique matches: {len(matched):,}")

# Show samples
print("\nSample matches:")
for _, row in matched.head(20).iterrows():
    rid = int(row['id'])
    name = str(row['name'] or '')[:45]
    print(f"  ID={rid} {name:<45} → {row['ISO_A2']} ({row['NAME']})")

# Batch update
ids = matched['id'].astype(int).tolist()
isos = matched['ISO_A2'].tolist()
mapping = list(zip(ids, isos))

c = conn.cursor()
c.execute("CREATE TEMP TABLE IF NOT EXISTS _zz_map (id INTEGER PRIMARY KEY, country TEXT)")
c.execute("DELETE FROM _zz_map")
for i in range(0, len(mapping), 1000):
    c.executemany("INSERT OR REPLACE INTO _zz_map VALUES (?, ?)", mapping[i:i+1000])

c.execute("""
    UPDATE churches SET country = (SELECT country FROM _zz_map WHERE id = churches.id)
    WHERE id IN (SELECT id FROM _zz_map)
""")
updated = c.rowcount
conn.commit()

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_geocode_zz_v2.py', TS, TS,
      updated, 0, 'country', 'completed',
      f'Geocoded {updated} ZZ→country via point-in-polygon (Natural Earth 50m)'))

conn.commit()

print(f"\nUpdated: {updated}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
print(f"Remaining ZZ: {c.fetchone()[0]:,}")
conn.close()
print("Done!")

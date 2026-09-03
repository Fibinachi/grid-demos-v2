"""
Fill missing county_fips_5 via spatial join to Census county boundaries.
Uses cached county shapefile at data/us_counties.geojson.
"""
import sqlite3, time
from datetime import datetime
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

DB = r'E:\grid\churches.db'
COUNTY_FILE = Path(r'E:\grid\data\us_counties.geojson')

print("Loading county boundaries...", end=' ', flush=True)
counties = gpd.read_file(COUNTY_FILE)
print(f'{len(counties):,} counties')

# Find the FIPS column
for col in counties.columns:
    cl = col.lower()
    if 'fips' in cl or 'geoid' in cl:
        fips_col = col
        break
else:
    fips_col = counties.columns[0]
print(f'FIPS column: {fips_col}')

# Ensure CRS
if counties.crs is None:
    counties = counties.set_crs('EPSG:4326')
elif str(counties.crs) != 'EPSG:4326':
    counties = counties.to_crs('EPSG:4326')

# Load churches missing county FIPS
db = sqlite3.connect(DB)
c = db.cursor()
c.execute("""SELECT id, latitude, longitude FROM churches 
    WHERE country='US' AND latitude IS NOT NULL 
    AND (county_fips_5 IS NULL OR county_fips_5 = '')""")
rows = c.fetchall()
print(f'{len(rows):,} churches missing county_fips_5')

if not rows:
    print('Nothing to do.')
    db.close()
    exit()

# Build GeoDataFrame (filter out any with empty/null coordinates)
valid_rows = []
for r in rows:
    try:
        lat = float(r[1]) if r[1] and r[1] != '' else None
        lon = float(r[2]) if r[2] and r[2] != '' else None
        if lat is not None and lon is not None:
            valid_rows.append((r[0], lat, lon))
    except (ValueError, TypeError):
        pass

print(f'  {len(valid_rows):,} with valid coordinates (filtered {len(rows)-len(valid_rows):,} bad)')

church_gdf = gpd.GeoDataFrame(
    [(r[0],) for r in valid_rows],
    columns=['id'],
    geometry=[Point(lon, lat) for _, lat, lon in valid_rows],
    crs='EPSG:4326'
)

# Spatial join
print('Spatial join...', end=' ', flush=True)
t0 = time.time()
joined = gpd.sjoin(church_gdf, counties[[fips_col, 'geometry']], how='inner', predicate='within')
elapsed = time.time() - t0
print(f'{len(joined):,} matched in {elapsed:.1f}s')

# Update churches table
print(f'  Joined columns: {list(joined.columns)[:8]}')
print('Updating churches...')
now = datetime.now().isoformat()
updated = 0

# The spatial join preserves the left index; our church_gdf index maps to valid_rows
for idx, row in joined.iterrows():
    church_id = int(valid_rows[idx][0])
    fips = str(row['id_right'])
    # Ensure 5-digit FIPS
    if len(fips) < 5:
        fips = fips.zfill(5)
    fips = fips[:5]
    
    c.execute("UPDATE churches SET county_fips_5 = ? WHERE id = ?", (fips, church_id))
    updated += 1
    if updated % 5000 == 0:
        db.commit()
        print(f'  {updated:,}/{len(joined):,}...')

db.commit()
print(f'  Updated {updated:,} churches')

# Verify
unmatched = len(rows) - len(joined)
c.execute("""SELECT COUNT(*) FROM churches 
    WHERE country='US' AND latitude IS NOT NULL 
    AND (county_fips_5 IS NULL OR county_fips_5 = '')""")
remaining = c.fetchone()[0]
print(f'\nUnmatched (likely offshore/coastal): {unmatched:,}')
print(f'Remaining without county_fips_5: {remaining:,}')

# Provenance
c.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, fields_populated, records_attempted, status)
    VALUES ('county_fips_proximity', 'fill_county_fips.py', ?, ?, ?, 'county_fips_5', ?, 'completed')""",
    (now, datetime.now().isoformat(), updated, updated))
db.commit()
db.close()
print('Done.')

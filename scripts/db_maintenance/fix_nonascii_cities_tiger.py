"""Fix remaining non-ASCII US cities via TIGER place boundary spatial join."""
import sqlite3, sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, log_change
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from datetime import datetime

PLACES_SHP = r'E:\grid\data\census_tiger\cb_2024_us_place_500k.shp'

print("Loading Census place boundaries...")
t0 = time.time()
places = gpd.read_file(PLACES_SHP)
places = places[['STATEFP', 'NAME', 'geometry']].copy()
places = places.set_crs('EPSG:4269', allow_override=True)
print(f"  {len(places):,} places in {time.time()-t0:.1f}s")

db = connect()
cur = db.cursor()

cur.execute("""
    SELECT rowid, id, latitude, longitude, name, city, state
    FROM churches
    WHERE country='US' AND city GLOB '*[^ -~]*'
      AND latitude IS NOT NULL AND latitude!=0
""")
rows = cur.fetchall()
print(f"\nNon-ASCII US records with GPS: {len(rows):,}")

if not rows:
    print("Nothing to fix!")
    db.close(); exit()

# Build GeoDataFrame
points = gpd.GeoDataFrame(
    {'rowid': [r[0] for r in rows], 'id': [r[1] for r in rows],
     'old_city': [r[5] for r in rows], 'state': [r[6] for r in rows]},
    geometry=[Point(r[3], r[2]) for r in rows],
    crs='EPSG:4269'
)

# Spatial join
print("Spatial joining...")
joined = gpd.sjoin(points, places[['NAME', 'geometry']], predicate='within', how='left')
matched = joined[joined['index_right'].notna()]

now = datetime.now().isoformat()
fixed = 0

for _, row in matched.iterrows():
    new_city = row['NAME']
    if not new_city or pd.isna(new_city):
        continue
    
    # Strip CDP/city/town suffix
    import re
    new_city = re.sub(r'\s+(city|town|village|borough|CDP)$', '', str(new_city), flags=re.IGNORECASE)
    
    cur.execute("UPDATE churches SET city=?, last_updated=? WHERE rowid=?", (new_city, now, int(row['rowid'])))
    log_change(db, church_id=int(row['id']), field_name="city", old_value=row['old_city'],
              new_value=new_city, source="tiger_reverse_geocode")
    fixed += 1

db.commit()

unmatched = len(rows) - fixed
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND city GLOB '*[^ -~]*'")
remaining = cur.fetchone()[0]

print(f"\nFixed: {fixed:,}  |  Unmatched: {unmatched:,}  |  Remaining non-ASCII: {remaining:,}")
db.close()
print("Done.")

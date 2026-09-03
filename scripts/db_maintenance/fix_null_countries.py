"""Fix remaining NULL countries via nearest-neighbor spatial join."""
import sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime

world = gpd.read_file("data/natural_earth/ne_10m_admin_0_countries.shp")
world = world[['ISO_A2', 'geometry']].dropna(subset=['ISO_A2'])
world = world[world.ISO_A2 != '-99']
print(f"Loaded {len(world)} countries")

db = connect()
cur = db.cursor()
cur.execute("SELECT id, latitude, longitude FROM churches WHERE country IS NULL AND latitude IS NOT NULL AND latitude != 0")
rows = cur.fetchall()
print(f"Remaining NULL: {len(rows)}")

if rows:
    points = gpd.GeoDataFrame(
        {'church_id': [r[0] for r in rows]},
        geometry=[Point(r[2], r[1]) for r in rows], crs="EPSG:4326"
    )
    joined = gpd.sjoin_nearest(points, world, how='left', max_distance=0.5, distance_col='dist')
    now = datetime.now().isoformat()
    fixed = 0
    for _, row in joined.iterrows():
        iso = row['ISO_A2']
        if iso and isinstance(iso, str) and len(iso) == 2:
            cur.execute("UPDATE churches SET country=?, last_updated=? WHERE id=?", (iso, now, row['church_id']))
            fixed += 1
    db.commit()
    print(f"Fixed: {fixed}")

cur.execute("SELECT COUNT(*) FROM churches WHERE country IS NULL")
print(f"Final NULL: {cur.fetchone()[0]}")
db.close()
print("Done.")

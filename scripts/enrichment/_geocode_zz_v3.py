"""
ZZ country assignment using manual spatial check (no sjoin).
Just iterate points and check which country polygon contains them.
"""
import sqlite3, geopandas as gpd, pandas as pd, datetime
from pathlib import Path
from shapely import contains

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
DATA_DIR = Path('data/shapefiles')

# Load world
world = gpd.read_file(DATA_DIR / 'ne_50m_admin_0_countries.shp')
world = world[['ISO_A2', 'NAME', 'geometry']].copy()
world = world[world['ISO_A2'] != '-99']
print(f"Countries: {len(world)}")

# Build spatial index for fast lookup
world_sindex = world.sindex

# Load ZZ records
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
c.execute("SELECT id, name, latitude, longitude FROM churches WHERE country='ZZ' AND latitude IS NOT NULL")
zz_records = c.fetchall()
print(f"ZZ records: {len(zz_records):,}")

# Point-in-polygon check
from shapely.geometry import Point

mapping = []
unmatched = []
for rid, name, lat, lon in zz_records:
    point = Point(lon, lat)
    found = False
    # Use spatial index to find candidate polygons
    candidates = list(world_sindex.intersection(point.bounds))
    for idx in candidates:
        if world.iloc[idx].geometry.contains(point):
            mapping.append((rid, world.iloc[idx]['ISO_A2']))
            found = True
            break
    if not found:
        # Try intersects (for border cases)
        for idx in candidates:
            if world.iloc[idx].geometry.intersects(point):
                mapping.append((rid, world.iloc[idx]['ISO_A2']))
                found = True
                break
    if not found:
        unmatched.append((rid, name, lat, lon))

print(f"Matched: {len(mapping):,}")
print(f"Unmatched: {len(unmatched):,}")

# Show samples
print("\nSample matches:")
for rid, iso in mapping[:15]:
    for rec in zz_records:
        if rec[0] == rid:
            print(f"  ID={rid} {str(rec[1])[:45]:<45} → {iso}")
            break

if unmatched:
    print(f"\nSample unmatched:")
    for rid, name, lat, lon in unmatched[:10]:
        print(f"  ID={rid} {str(name)[:45]:<45} ({lat:.4f}, {lon:.4f})")

# Batch update
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
""", ('manual', '_geocode_zz_v3.py', TS, TS,
      updated, 0, 'country', 'completed',
      f'Manual point-in-polygon: {updated} ZZ→country (Natural Earth 50m)'))

conn.commit()

print(f"\nUpdated: {updated}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='ZZ'")
print(f"Remaining ZZ: {c.fetchone()[0]:,}")
conn.close()
print("Done!")

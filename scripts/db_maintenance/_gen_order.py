"""Produce the new REGION_ORDER block to paste into _import_osm_all.py"""
import sqlite3
from shapely import wkb
from shapely.geometry import box

TILE = 0.5
gconn = sqlite3.connect('data/natural_earth/world_borders.db')
gc = gconn.cursor()
gc.execute("SELECT iso_a2, name, geometry_wkb FROM world_borders WHERE iso_a2 NOT IN ('-99','') AND iso_a2 IS NOT NULL")

results = []
for iso, name, blob in gc.fetchall():
    try:
        poly = wkb.loads(blob)
        mx, my, Mx, My = poly.bounds
    except: continue
    subs = [(my, mx, My, Mx)]
    if My - my > 20 or Mx - mx > 40:
        subs = []
        lat = my
        while lat < My:
            lon = mx
            while lon < Mx:
                subs.append((lat, lon, min(lat + 15, My), min(lon + 30, Mx)))
                lon += 30
            lat += 15
    land_tiles = 0
    for s, w, n, e in subs:
        tlat = s
        while tlat < n:
            tlon = w
            while tlon < e:
                tile_box = box(tlon, tlat, min(tlon + TILE, e), min(tlat + TILE, n))
                if poly.intersects(tile_box):
                    land_tiles += 1
                tlon += TILE
            tlat += TILE
    results.append((iso, name, land_tiles))
gconn.close()
results.sort(key=lambda r: r[2])

with open('_tile_order_out.txt', 'w') as f:
    f.write("REGION_ORDER = {\n")
    for i, (iso, name, tiles) in enumerate(results):
        f.write(f'    "{iso}": {i+1},  # {name} ({tiles:,})\n')
    f.write("}\n")

print(f"Written {len(results)} entries to _tile_order_out.txt")
print(f"Total land tiles: {sum(r[2] for r in results):,}")

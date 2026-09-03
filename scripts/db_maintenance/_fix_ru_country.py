"""Fix RU→actual_country for osm_import churches mis-tagged as Russia."""
import sqlite3, json
from shapely.geometry import Point
from shapely import wkb
from shapely.strtree import STRtree
from collections import Counter

# Load world borders
bconn = sqlite3.connect('data/natural_earth/world_borders.db')
bc = bconn.cursor()
bc.execute('SELECT iso_a2, name, geometry_wkb FROM world_borders WHERE iso_a2 IS NOT NULL')
borders_list = []
for iso, name, geom_wkb in bc.fetchall():
    if geom_wkb:
        try:
            geom = wkb.loads(geom_wkb)
            borders_list.append((iso, name, geom))
        except:
            pass
bconn.close()
print(f'Loaded {len(borders_list)} country polygons')

geoms_only = [g for _, _, g in borders_list]
tree = STRtree(geoms_only)

# Get Russia polygon
russia_geom = None
for iso, name, geom in borders_list:
    if iso == 'RU':
        russia_geom = geom
        break

# Query all RU churches with coords
conn = sqlite3.connect('churches.db')
c = conn.cursor()
c.execute("SELECT rowid, latitude, longitude FROM churches WHERE country='RU' AND latitude IS NOT NULL AND longitude IS NOT NULL")
print('Checking RU churches...')

fixes = Counter()
to_update = []  # (actual_cc, rowid)
total = 0
batch = 0

for row in c:
    total += 1
    batch += 1
    if batch >= 50000:
        print(f'  Processed {total:,}... fixes so far: {sum(fixes.values()):,}')
        batch = 0
    
    rowid, lat, lon = row[0], row[1], row[2]
    pt = Point(lon, lat)
    
    # First check if in Russia
    if russia_geom and russia_geom.contains(pt):
        continue  # correctly tagged
    
    # Find actual country
    candidates = tree.query(pt)
    for idx in candidates:
        if geoms_only[idx].contains(pt):
            actual_cc = borders_list[idx][0]
            fixes[actual_cc] += 1
            to_update.append((actual_cc, rowid))
            break

print(f'\nTotal RU checked: {total:,}')
print(f'Need country fix: {sum(fixes.values()):,}')
print()
for cc, count in fixes.most_common(40):
    name = next((n for i, n, g in borders_list if i == cc), '?')
    print(f'  RU->{cc}: {count:>8,d}  {name}')

with open('_ru_fixes.json', 'w') as f:
    json.dump({'fixes': dict(fixes.most_common()), 'total': len(to_update)}, f)
print(f'\nSaved fix summary. Ready to apply {len(to_update):,} updates.')

conn.close()

"""Apply RU→actual_country fixes - collect all, then batch update."""
import sqlite3
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
russia_geom = next((geom for iso, name, geom in borders_list if iso == 'RU'), None)

# PHASE 1: Collect all mismatches (NO writes during SELECT)
conn = sqlite3.connect('churches.db')
c = conn.cursor()
c.execute("SELECT rowid, latitude, longitude FROM churches WHERE country='RU' AND latitude IS NOT NULL AND longitude IS NOT NULL")
print('Collecting RU mismatches...')

fixes = Counter()
updates = []  # (actual_cc, rowid)
total = 0
batch = 0

for row in c:
    total += 1
    batch += 1
    if batch >= 50000:
        print(f'  Checked {total:,}... mismatches so far: {len(updates):,}')
        batch = 0
    
    rowid, lat, lon = row[0], row[1], row[2]
    pt = Point(lon, lat)
    
    if russia_geom and russia_geom.contains(pt):
        continue
    
    candidates = tree.query(pt)
    for idx in candidates:
        if geoms_only[idx].contains(pt):
            actual_cc = borders_list[idx][0]
            fixes[actual_cc] += 1
            updates.append((actual_cc, rowid))
            break

conn.close()

print(f'\nTotal RU checked: {total:,}')
print(f'Mismatches to fix: {len(updates):,}')
print(f'Actually in Russia: {total - len(updates):,}')

# PHASE 2: Apply all updates
print(f'\nApplying {len(updates):,} updates...')
from gw_db import connect as gw_connect, Provenance
gwconn = gw_connect()

with Provenance(gwconn, 'fix_ru_country_spatial', source='manual', fields='country'):
    gc = gwconn.cursor()
    chunk = 50000
    for i in range(0, len(updates), chunk):
        b = updates[i:i+chunk]
        gc.executemany("UPDATE churches SET country=? WHERE rowid=?", b)
        if i % 100000 == 0:
            print(f'  Applied {i:,} / {len(updates):,}...')
    print(f'  Applied all {len(updates):,} updates')

gwconn.commit()
gwconn.close()

print('\nSummary:')
for cc, count in fixes.most_common(40):
    name = next((n for i, n, g in borders_list if i == cc), '?')
    print(f'  RU->{cc}: {count:>8,d}  {name}')

print('\nDone!')

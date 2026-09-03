"""Audit checkpoint for multi-section countries with bare ISO codes."""
import sqlite3
from shapely import wkb

CHECKPOINT = 'E:/grid/_osm_checkpoint.txt'
GEO = 'E:/grid/data/natural_earth/world_borders.db'

with open(CHECKPOINT) as f:
    ckpt_lines = [l.strip() for l in f if l.strip()]

bare = {l for l in ckpt_lines if '-' not in l}
section_keys = {l for l in ckpt_lines if '-' in l}

print(f'Total checkpoint lines: {len(ckpt_lines)}')
print(f'Bare ISO codes: {len(bare)}')
print(f'Section keys: {len(section_keys)}')

gconn = sqlite3.connect(GEO)
gc = gconn.cursor()
gc.execute('SELECT iso_a2,name,geometry_wkb FROM world_borders WHERE iso_a2 NOT IN (\'-99\',\'\') AND iso_a2 IS NOT NULL')

print('\nMulti-section countries in checkpoint:')
found_any = False
for iso, name, blob in gc.fetchall():
    try:
        poly = wkb.loads(blob)
        mx, my, Mx, My = poly.bounds
    except:
        continue
    if My - my > 20 or Mx - mx > 40:
        # Count sections
        subs_lat = 0
        lat = my
        while lat < My:
            lon = mx
            while lon < Mx:
                subs_lat += 1
                lon += 30
            lat += 15
        has_bare = iso in bare
        has_section = any(s.startswith(f'{iso}-') for s in section_keys)
        if has_bare or has_section:
            found_any = True
            section_count = sum(1 for s in section_keys if s.startswith(f'{iso}-'))
            status = 'OK' if has_section and not has_bare else 'BAD - bare code needs removal' if has_bare else 'OK - has section keys only'
            print(f'  {iso:4s} {name:35s} {subs_lat:3d} secs  bare={int(has_bare)} section_keys={section_count}  [{status}]')

if not found_any:
    print('  (none)')

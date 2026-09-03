"""Verify all multi-section countries are handled in checkpoint."""
import sqlite3
from shapely import wkb

CHECKPOINT = 'E:/grid/_osm_checkpoint.txt'
GEO = 'E:/grid/data/natural_earth/world_borders.db'

with open(CHECKPOINT) as f:
    ckpt_lines = [l.strip() for l in f if l.strip()]

bare = {l for l in ckpt_lines if '-' not in l}
section_keys = {l for l in ckpt_lines if '-' in l}

gconn = sqlite3.connect(GEO)
gc = gconn.cursor()
gc.execute('SELECT iso_a2,name,geometry_wkb FROM world_borders WHERE iso_a2 NOT IN (\'-99\',\'\') AND iso_a2 IS NOT NULL')

multi_section = []
for iso, name, blob in gc.fetchall():
    try:
        poly = wkb.loads(blob)
        mx, my, Mx, My = poly.bounds
    except:
        continue
    if My - my > 20 or Mx - mx > 40:
        multi_section.append((iso, name))

# Count expected sections
print(f'Multi-section countries not yet fully checkpointed:')
print(f'{"ISO":4s} {"Name":35s} {"Exp":4s} {"In Ckpt":8s} {"Need":}')
print('-' * 65)
for iso, name in multi_section:
    if iso in bare or any(s.startswith(f'{iso}-') for s in section_keys):
        if iso in bare:
            # Country had bare ISO - sections beyond 1 need re-scan
            gconn2 = sqlite3.connect(GEO)
            gc2 = gconn2.cursor()
            gc2.execute('SELECT geometry_wkb FROM world_borders WHERE iso_a2=?', (iso,))
            blob = gc2.fetchone()[0]
            poly = wkb.loads(blob)
            mx, my, Mx, My = poly.bounds
            subs = []
            lat = my
            while lat < My:
                lon = mx
                while lon < Mx:
                    subs.append(1)
                    lon += 30
                lat += 15
            total_secs = len(subs)
            print(f'{iso:4s} {name:35s} {total_secs:3d}  bare code   {"section 2+" if total_secs > 1 else "OK":>10s}')
            gconn2.close()
        else:
            section_nums = set()
            for s in section_keys:
                if s.startswith(f'{iso}-'):
                    sec_num = int(s.split('-')[1])
                    section_nums.add(sec_num)
            max_sec = max(section_nums) if section_nums else 0
            
            # Total sections
            gconn2 = sqlite3.connect(GEO)
            gc2 = gconn2.cursor()
            gc2.execute('SELECT geometry_wkb FROM world_borders WHERE iso_a2=?', (iso,))
            blob = gc2.fetchone()[0]
            poly = wkb.loads(blob)
            mx, my, Mx, My = poly.bounds
            subs = []
            lat = my
            while lat < My:
                lon = mx
                while lon < Mx:
                    subs.append(1)
                    lon += 30
                lat += 15
            total_secs = len(subs)
            remaining = total_secs - max_sec
            if remaining > 0:
                print(f'{iso:4s} {name:35s} {total_secs:3d}  secs 1-{max_sec}  +{remaining} remaining')
            else:
                print(f'{iso:4s} {name:35s} {total_secs:3d}  secs 1-{max_sec}  COMPLETE')
            gconn2.close()
    else:
        # Not in checkpoint at all - need full scan
        gconn2 = sqlite3.connect(GEO)
        gc2 = gconn2.cursor()
        gc2.execute('SELECT geometry_wkb FROM world_borders WHERE iso_a2=?', (iso,))
        blob = gc2.fetchone()[0]
        poly = wkb.loads(blob)
        mx, my, Mx, My = poly.bounds
        subs = []
        lat = my
        while lat < My:
            lon = mx
            while lon < Mx:
                subs.append(1)
                lon += 30
            lat += 15
        total_secs = len(subs)
        print(f'{iso:4s} {name:35s} {total_secs:3d}  NONE        full scan ({total_secs} secs)')
        gconn2.close()

gconn.close()

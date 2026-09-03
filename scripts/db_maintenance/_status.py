"""Quick scraper status check."""
import sqlite3
from shapely import wkb
from shapely.geometry import box

TILE = 0.5

with open('_osm_checkpoint.txt') as f:
    lines = [l.strip() for l in f if l.strip()]

done = set(lines)
old_batch_end = 133  # approximate
new_done = len(lines) - old_batch_end
print(f"Checkpoint: {len(lines)} total, ~{new_done} new since batch restart")

# Get remaining codes
gconn = sqlite3.connect('data/natural_earth/world_borders.db')
gc = gconn.cursor()
gc.execute("SELECT iso_a2, name FROM world_borders WHERE iso_a2 NOT IN ('-99','') AND iso_a2 IS NOT NULL")
all_codes = {r[0]: r[1] for r in gc.fetchall()}
remaining_codes = sorted([c for c in all_codes if c not in done])
print(f"Remaining: {len(remaining_codes)} countries")

# Count tiles for remaining
total_tiles = 0
for code in remaining_codes:
    gc.execute('SELECT geometry_wkb FROM world_borders WHERE iso_a2=?', (code,))
    row = gc.fetchone()
    if not row:
        continue
    try:
        poly = wkb.loads(row[0])
        mx, my, Mx, My = poly.bounds
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
        for s, w, n, e in subs:
            tlat = s
            while tlat < n:
                tlon = w
                while tlon < e:
                    tile_box = box(tlon, tlat, min(tlon + TILE, e), min(tlat + TILE, n))
                    if poly.intersects(tile_box):
                        total_tiles += 1
                    tlon += TILE
                tlat += TILE
    except:
        pass

gconn.close()
print(f"Remaining tiles: {total_tiles:,}")

# Show next 10 upcoming (first 10 remaining)
print(f"\nNext up ({min(10, len(remaining_codes))}):")
for code in remaining_codes[:10]:
    name = all_codes.get(code, '?')
    print(f"  {code} {name}")

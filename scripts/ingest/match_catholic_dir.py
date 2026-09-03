"""
Proximity-match Catholic directory entries (dir_entries) against GRID churches.
Uses bounding box + state filter for speed.

Strategy:
  - Build state-indexed dict of GRID churches
  - For each Catholic entry, compute bounding box (±0.005° ≈ 500m)
  - Filter candidates to those within the box first, then exact haversine
  - Update grid_church_id on dir_entries
"""
import sqlite3, math, time
from collections import defaultdict

CATH_DB = 'E:/grid/data/catholic_directory.db'
GRID_DB = 'E:/grid/churches.db'
THRESHOLD_KM = 0.3
BBOX_DEG = 0.005  # ~500m at mid-latitudes

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def progress_bar(current, total, width=40):
    if total == 0:
        return f"[{'█'*width}] {current}/{current} (100%)"
    pct = current / total
    filled = int(width * pct)
    return f"[{'█'*filled}{'░'*(width-filled)}] {current}/{total} ({pct*100:.0f}%)"

cath = sqlite3.connect(CATH_DB)
cath.row_factory = sqlite3.Row
grid = sqlite3.connect(GRID_DB)
grid.row_factory = sqlite3.Row

# Load Catholic directory entries with GPS
cath_rows = cath.execute('''
    SELECT id, name, city, state, latitude, longitude, entity_type, directory_year
    FROM dir_entries
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    ORDER BY id
''').fetchall()
print(f'Catholic directory GPS records: {len(cath_rows):,}')

# Load GRID churches with GPS into memory
grid_rows = grid.execute('''
    SELECT id, city, state, latitude, longitude
    FROM churches
    WHERE latitude IS NOT NULL AND latitude != 0
      AND longitude IS NOT NULL AND longitude != 0
''').fetchall()
print(f'GRID churches with GPS: {len(grid_rows):,}')

# Build state-index of GRID churches
# Each entry: (lat, lon, id, city_upper)
state_idx = defaultdict(list)
for g in grid_rows:
    st = (g['state'] or '').strip().upper()
    state_idx[st].append((
        g['latitude'], g['longitude'],
        g['id'],
        (g['city'] or '').strip().upper()
    ))
print(f'States with GRID data: {len(state_idx)}')

# For states with very many churches, also build a spatial grid
# But for now, we'll use bounding box filtering on the state list

t0 = time.time()
matched = 0
total = 0
updates = []

for cr in cath_rows:
    total += 1
    clat = cr['latitude']
    clon = cr['longitude']
    state = (cr['state'] or '').strip().upper()
    city = (cr['city'] or '').strip().upper()
    
    cands = state_idx.get(state, [])
    if not cands:
        continue
    
    # Bounding box filter
    lat_min, lat_max = clat - BBOX_DEG, clat + BBOX_DEG
    lon_min, lon_max = clon - BBOX_DEG, clon + BBOX_DEG
    
    best_dist = float('inf')
    best_id = None
    best_city = ''
    
    for glat, glon, gid, gcity in cands:
        if lat_min <= glat <= lat_max and lon_min <= glon <= lon_max:
            d = haversine_km(clat, clon, glat, glon)
            if d < best_dist:
                best_dist = d
                best_id = gid
                best_city = gcity
    
    if best_id and best_dist <= THRESHOLD_KM:
        matched += 1
        same_city = (best_city == city) if city else False
        conf = 'high' if same_city else 'medium'
        updates.append((best_id, f'proximity_{conf}_{best_dist*1000:.0f}m', cr['id']))
    
    if total % 5000 == 0:
        print(f'  {progress_bar(total, len(cath_rows))} matched: {matched}', flush=True)

if updates:
    cath.executemany('''
        UPDATE dir_entries
        SET grid_church_id = ?, geocode_confidence = ?
        WHERE id = ?
    ''', updates)
    cath.commit()

elapsed = time.time() - t0
print(f'\n  {progress_bar(total, len(cath_rows))} matched: {matched}')
print(f'\nDone in {elapsed:.1f}s ({len(cath_rows)/elapsed:.0f} rec/s)')
print(f'Matched: {matched}/{len(cath_rows)} ({100*matched/len(cath_rows):.1f}%)')

# Summary by year
print('\nBy year:')
for r in cath.execute('SELECT directory_year, COUNT(*) as t, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m FROM dir_entries WHERE latitude IS NOT NULL GROUP BY directory_year ORDER BY directory_year').fetchall():
    print(f'  {r["directory_year"]}: {r["m"]}/{r["t"]} ({100*r["m"]/r["t"]:.0f}%)')

# Summary by geocode source
print('\nBy geocode source:')
for r in cath.execute('SELECT geocode_source, COUNT(*) as t, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m FROM dir_entries WHERE latitude IS NOT NULL AND geocode_source IS NOT NULL GROUP BY geocode_source ORDER BY t DESC').fetchall():
    print(f'  {r["geocode_source"]}: {r["m"]}/{r["t"]} ({100*r["m"]/r["t"]:.0f}%)')

# Summary by entity type
print('\nBy entity type:')
for r in cath.execute('SELECT entity_type, COUNT(*) as t, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as m FROM dir_entries WHERE latitude IS NOT NULL GROUP BY entity_type ORDER BY t DESC LIMIT 10').fetchall():
    print(f'  {r["entity_type"]}: {r["m"]}/{r["t"]} ({100*r["m"]/r["t"]:.0f}%)')

cath.close()
grid.close()
print('\nDone.')

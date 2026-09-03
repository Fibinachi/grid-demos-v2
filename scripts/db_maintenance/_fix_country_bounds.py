"""Fix country assignments using coordinate bounding boxes. Fast, no BQ needed."""
import sqlite3
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')

print('=== CURRENT COUNTRY COUNTS ===')
for r in conn.execute('SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC'):
    print(f'  {r[0] or "NULL":5s} {r[1]:>10,}')

# Country bounds (approximate, covers continental territory)
# US lower 48 + Alaska
US_BOUNDS = {'lat_min': 24.0, 'lat_max': 49.5, 'lon_min': -125.0, 'lon_max': -66.0}
# Alaska
AK_BOUNDS = {'lat_min': 51.0, 'lat_max': 72.0, 'lon_min': -180.0, 'lon_max': -130.0}
# Canada
CA_BOUNDS = {'lat_min': 41.0, 'lat_max': 83.0, 'lon_min': -141.0, 'lon_max': -52.0}
# Mexico
MX_BOUNDS = {'lat_min': 14.0, 'lat_max': 33.0, 'lon_min': -118.0, 'lon_max': -86.0}

def in_bounds(lat, lon, b):
    return b['lat_min'] <= lat <= b['lat_max'] and b['lon_min'] <= lon <= b['lon_max']

def determine_country(lat, lon):
    """Return correct country code based on coordinates."""
    if in_bounds(lat, lon, US_BOUNDS) or in_bounds(lat, lon, AK_BOUNDS):
        return 'US'
    if in_bounds(lat, lon, MX_BOUNDS) and not in_bounds(lat, lon, US_BOUNDS):
        return 'MX'
    if in_bounds(lat, lon, CA_BOUNDS) and not in_bounds(lat, lon, US_BOUNDS):
        return 'CA'
    return None  # can't determine

# Check all churches with coords
rows = conn.execute("SELECT id, latitude, longitude, country FROM churches WHERE latitude IS NOT NULL").fetchall()
print(f'\nChecking {len(rows):,} churches...')

mismatches = []
for id_, lat, lon, old_country in rows:
    if not lat or not lon:
        continue
    actual = determine_country(lat, lon)
    if actual and actual != old_country:
        mismatches.append((actual, old_country, id_))

print(f'Churches with wrong country: {len(mismatches):,}')
if mismatches:
    from collections import Counter
    changes = Counter(f'{old}->{new}' for new, old, _ in mismatches)
    for change, count in changes.most_common():
        print(f'  {change}: {count:,}')

    # Update
    conn.executemany("UPDATE churches SET country=? WHERE id=?", 
                     [(new, cid) for new, _, cid in mismatches])
    conn.commit()
    print(f'\nUpdated {len(mismatches):,} churches')
else:
    print('No mismatches found')

print('\n=== CORRECTED COUNTRY COUNTS ===')
for r in conn.execute('SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC'):
    print(f'  {r[0] or "NULL":5s} {r[1]:>10,}')

# Show samples of fixes
print('\n=== US churches that were CA/MX ===')
for r in conn.execute("SELECT name, city, state, country FROM churches WHERE state IN ('ON','QC','BC','CMX','SLP','BCS') LIMIT 8").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]:5s} country={r[3]}')

# Show true CA/MX churches
print('\n=== TRUE CANADIAN CHURCHES ===')
for r in conn.execute("SELECT name, city, state FROM churches WHERE country='CA' LIMIT 5").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]}')

print('\n=== TRUE MEXICAN CHURCHES ===')
for r in conn.execute("SELECT name, city, state FROM churches WHERE country='MX' LIMIT 5").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]}')

total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'\nTOTAL: {total:,}')
conn.close()
print('Done.')

"""
VERMONT DATA CLEANUP — Fix city names, counties, state codes, and remove bad records.
Runs in 5 phases.
"""
import sqlite3, re, time
from collections import defaultdict

DB_PATH = 'churches.db'
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")

VT_BBOX = (42.7, 45.1, -73.5, -71.4)  # lat_min, lat_max, lon_min, lon_max
VT_COUNTIES = {'Addison','Bennington','Caledonia','Chittenden','Essex','Franklin',
               'Grand Isle','Lamoille','Orange','Orleans','Rutland','Washington','Windham','Windsor'}

# ============================================================
# PHASE 1: Fix "Istanbul" → reverse geocode from GPS
# ============================================================
print("=== PHASE 1: Fix 'Istanbul' city (reverse geocode from GPS) ===")

# We need a city lookup. Use existing VT records to build coordinate→city map
coord_to_city = {}
for r in db.execute("""
    SELECT city, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' 
    AND city NOT IN ('Istanbul','Matsuyama','Fukuoka','Tokushima','Takamatsu','Shimonoseki','Kochi')
    AND city IS NOT NULL AND city != ''
    AND latitude IS NOT NULL
"""):
    key = (round(r['latitude'], 3), round(r['longitude'], 3))
    if key not in coord_to_city:
        coord_to_city[key] = r['city']

# Also add known VT cities from NH records
for r in db.execute("""
    SELECT city, latitude, longitude FROM churches 
    WHERE state IN ('NH','New Hampshire') AND country='US'
    AND latitude BETWEEN 42.7 AND 45.1 
    AND longitude BETWEEN -73.5 AND -71.4
    AND city IS NOT NULL AND city != ''
"""):
    key = (round(r['latitude'], 3), round(r['longitude'], 3))
    if key not in coord_to_city:
        coord_to_city[key] = r['city']

print(f'  Built coordinate→city map: {len(coord_to_city):,} entries')

# Fix Istanbul records
fixed_istanbul = 0
istanbul_records = db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul'
""").fetchall()

updates = []
for r in istanbul_records:
    if r['latitude'] and r['longitude']:
        key = (round(r['latitude'], 3), round(r['longitude'], 3))
        new_city = coord_to_city.get(key)
        if not new_city:
            # Try broader rounding
            key2 = (round(r['latitude'], 2), round(r['longitude'], 2))
            new_city = coord_to_city.get(key2)
        if new_city and new_city != 'Istanbul':
            updates.append((new_city, r['id']))
            fixed_istanbul += 1

db.executemany("UPDATE churches SET city=? WHERE id=?", updates)
db.commit()
print(f'  Fixed {fixed_istanbul}/{len(istanbul_records)} Istanbul records')

# ============================================================
# PHASE 2: Fix Japanese city names — parse from church name
# ============================================================
print("\n=== PHASE 2: Fix Japanese city names (parse from church names) ===")

jp_cities = ['Matsuyama','Fukuoka','Tokushima','Takamatsu','Shimonoseki','Kochi']

# Build set of all VT city names for validation
vt_city_set = set()
for r in db.execute("""
    SELECT DISTINCT city FROM churches 
    WHERE state IN ('VT','Vermont','NH','New Hampshire') AND country='US'
    AND city IS NOT NULL AND city != ''
"""):
    vt_city_set.add(r['city'].upper())

# Also add known VT town names
vt_towns = {
    'ARLINGTON','BENNINGTON','BRATTLEBORO','BURLINGTON','COLCHESTER','ESSEX','FRANKLIN',
    'HARTFORD','LEICESTER','MIDDLEBURY','MONTPELIER','MORRISVILLE','NEWPORT','NORWICH',
    'RANDOLPH','READSBORO','RUTLAND','SAINT ALBANS','ST ALBANS','ST JOHNSBURY','SAINT JOHNSBURY',
    'SHELBURNE','SPRINGFIELD','STOWE','SWANTON','WATERBURY','WILLISTON','WINOOSKI','WOODSTOCK',
    'BARRE','BELLOWS FALLS','BRANDON','BRISTOL','CASTLETON','CHARLOTTE','CHELSEA','CHESTER',
    'DANVILLE','DORSET','ENOSBURG','FAIRFAX','GEORGIA','GRAND ISLE','GREENSBORO','HARDWICK',
    'HIGHGATE','HINESBURG','HYDE PARK','JERICHO','JOHNSON','LUDLOW','LYNDONVILLE','MANCHESTER',
    'MIDDLESEX','MILTON','MORETOWN','NORTHFIELD','PITTSFORD','POULTNEY','PROCTOR','PUTNEY',
    'RICHFORD','RICHMOND','ROCKINGHAM','ROYALTON','SHARON','SHELDON','SOUTH BURLINGTON',
    'STARKSBORO','STRAFFORD','THETFORD','TOPSHAM','TOWNSHEND','TUNBRIDGE','UNDERHILL',
    'VERGENNES','WALLINGFORD','WARDSBORO','WATERFORD','WEATHERSFIELD','WELLS','WESTMINSTER',
    'WILMINGTON','WINDSOR','WOLCOTT'
}
vt_city_set.update(vt_towns)

def extract_city_from_name(name):
    """Try to extract VT city/town from church name."""
    if not name:
        return None
    name_upper = name.upper()
    
    # Pattern: "SAINT X CHURCH FRANKLIN" → Franklin
    # Pattern: "SAINT MICHAELS COLLEGE CHAPEL COLCHESTER" → Colchester
    # Pattern: "SAINT JOACHIM READSBORO" → Readsboro
    
    # Try known VT towns first (longest match first)
    sorted_towns = sorted(vt_towns, key=len, reverse=True)
    for town in sorted_towns:
        if town in name_upper:
            # Verify it's at the end or followed by a non-word boundary
            idx = name_upper.find(town)
            after = name_upper[idx + len(town):]
            if not after or not after[0].isalpha():
                return town.title()
    
    # Try multi-word patterns
    # "CHURCH IN LEICESTER" → Leicester
    m = re.search(r'(?:CHURCH|PARISH|CATHOLIC)\s+(?:IN|OF)\s+(\w+(?:\s+\w+)?)', name_upper)
    if m:
        candidate = m.group(1).title()
        if candidate.upper() in vt_city_set:
            return candidate
    
    return None

fixed_jp = 0
jp_records = db.execute(f"""
    SELECT id, name, city FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ({','.join(['?']*len(jp_cities))})
""", jp_cities).fetchall()

jp_updates = []
for r in jp_records:
    new_city = extract_city_from_name(r['name'])
    if new_city:
        jp_updates.append((new_city, r['id']))
        fixed_jp += 1

db.executemany("UPDATE churches SET city=? WHERE id=?", jp_updates)
db.commit()
print(f'  Fixed {fixed_jp}/{len(jp_records)} Japanese-named city records')

# Show what couldn't be fixed
unfixed = db.execute(f"""
    SELECT id, name, city FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ({','.join(['?']*len(jp_cities))})
""", jp_cities).fetchall()
if unfixed:
    print(f'  Still unfixed: {len(unfixed)}')
    for r in unfixed[:5]:
        print(f'    id={r["id"]} city={r["city"]} name={r["name"][:70]}')

# ============================================================
# PHASE 3: Fix state code normalization
# ============================================================
print("\n=== PHASE 3: State code normalization ===")

# "Vermont" → "VT", "New Hampshire" → "NH"
state_fixes = [
    ('Vermont', 'VT'),
    ('New Hampshire', 'NH'),
    ('New York', 'NY'),
    ('Massachusetts', 'MA'),
]
for old, new in state_fixes:
    n = db.execute("UPDATE churches SET state=? WHERE country='US' AND state=?", [new, old]).rowcount
    if n:
        print(f'  {old} → {new}: {n:,}')

db.commit()

# ============================================================
# PHASE 4: Fix records with coords outside VT bounding box
# ============================================================
print("\n=== PHASE 4: Fix out-of-bounds records ===")

# For each record outside VT bbox, try to determine correct state from coordinates
# We'll use a simple state bounding box lookup

# Simple US state bounding boxes (approximate)
STATE_BBOXES = {
    'AL': (30.1, 35.0, -88.5, -84.9), 'AK': (54.0, 71.5, -179.0, -130.0),
    'AZ': (31.3, 37.0, -114.8, -109.0), 'AR': (33.0, 36.5, -94.6, -89.6),
    'CA': (32.5, 42.0, -124.4, -114.1), 'CO': (37.0, 41.0, -109.1, -102.0),
    'CT': (40.9, 42.1, -73.7, -71.8), 'DE': (38.4, 39.9, -75.8, -75.0),
    'FL': (24.4, 31.0, -87.6, -80.0), 'GA': (30.3, 35.0, -85.6, -80.8),
    'HI': (18.9, 22.3, -160.3, -154.8), 'ID': (42.0, 49.0, -117.2, -111.0),
    'IL': (36.9, 42.5, -91.5, -87.5), 'IN': (37.8, 41.8, -88.1, -84.8),
    'IA': (40.4, 43.5, -96.6, -90.1), 'KS': (37.0, 40.0, -102.1, -94.6),
    'KY': (36.5, 39.2, -89.6, -82.0), 'LA': (28.9, 33.0, -94.0, -89.0),
    'ME': (43.0, 47.5, -71.1, -66.9), 'MD': (37.9, 39.8, -79.5, -75.0),
    'MA': (41.2, 42.9, -73.5, -69.9), 'MI': (41.7, 47.5, -90.4, -82.1),
    'MN': (43.5, 49.4, -97.2, -89.5), 'MS': (30.1, 35.0, -91.7, -88.1),
    'MO': (36.0, 40.6, -95.8, -89.1), 'MT': (44.4, 49.0, -116.1, -104.0),
    'NE': (40.0, 43.0, -104.1, -95.3), 'NV': (35.0, 42.0, -120.0, -114.0),
    'NH': (42.7, 45.3, -72.6, -70.6), 'NJ': (38.9, 41.4, -75.6, -73.9),
    'NM': (31.3, 37.0, -109.1, -103.0), 'NY': (40.5, 45.0, -79.8, -71.9),
    'NC': (33.8, 36.6, -84.3, -75.4), 'ND': (45.9, 49.0, -104.1, -96.6),
    'OH': (38.4, 42.0, -84.8, -80.5), 'OK': (33.6, 37.0, -103.0, -94.4),
    'OR': (42.0, 46.3, -124.6, -116.5), 'PA': (39.7, 42.3, -80.5, -74.7),
    'RI': (41.1, 42.0, -71.9, -71.1), 'SC': (32.0, 35.2, -83.4, -78.5),
    'SD': (42.5, 45.9, -104.1, -96.4), 'TN': (34.9, 36.7, -90.3, -81.6),
    'TX': (25.8, 36.5, -106.7, -93.5), 'UT': (37.0, 42.0, -114.1, -109.0),
    'VT': (42.7, 45.1, -73.5, -71.4), 'VA': (36.5, 39.5, -83.7, -75.2),
    'WA': (45.5, 49.0, -124.8, -116.9), 'WV': (37.2, 40.6, -82.6, -77.7),
    'WI': (42.5, 47.1, -92.9, -86.8), 'WY': (41.0, 45.0, -111.1, -104.0),
    'DC': (38.8, 39.0, -77.1, -76.9),
}

def find_state(lat, lon):
    """Find the best matching US state for given coordinates."""
    if lat is None or lon is None:
        return None
    best = None
    for st, (min_lat, max_lat, min_lon, max_lon) in STATE_BBOXES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return st  # Exact match
    return None

# Fix VT records with coords outside VT
out_of_bounds = db.execute("""
    SELECT id, name, city, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US'
    AND latitude IS NOT NULL
    AND (latitude NOT BETWEEN 42.7 AND 45.1 OR longitude NOT BETWEEN -73.5 AND -71.4)
""").fetchall()

print(f'  Records outside VT bbox: {len(out_of_bounds)}')

state_updates = []
delete_ids = []
for r in out_of_bounds:
    new_state = find_state(r['latitude'], r['longitude'])
    if new_state:
        state_updates.append((new_state, r['id']))
    else:
        # Couldn't determine state — delete
        delete_ids.append(r['id'])

if state_updates:
    db.executemany("UPDATE churches SET state=? WHERE id=?", state_updates)

if delete_ids:
    # Don't actually delete, just mark for review
    print(f'  WARNING: {len(delete_ids)} records could not be mapped to any state')

db.commit()

# Summarize what moved where
for r in db.execute("""
    SELECT state, COUNT(*) as n FROM churches 
    WHERE id IN ({})
    GROUP BY state ORDER BY n DESC
""".format(','.join(['?']*len(state_updates))), [s[0] for s in state_updates]):
    print(f'  → {r["state"]}: {r["n"]:,}')

print(f'  State fixes applied: {len(state_updates)}')

# ============================================================
# PHASE 5: Fix county assignments
# ============================================================
print("\n=== PHASE 5: County fixes ===")

# Fix non-VT counties → NULL (they need proper reverse geocoding)
bad_cty = 0
for r in db.execute("""
    SELECT DISTINCT county FROM churches 
    WHERE state='VT' AND country='US' 
    AND county IS NOT NULL AND county != ''
    AND county NOT IN ({})
""".format(','.join(['?']*len(VT_COUNTIES))), list(VT_COUNTIES)):
    n = db.execute("UPDATE churches SET county=NULL WHERE state='VT' AND country='US' AND county=?", [r['county']]).rowcount
    bad_cty += n
    print(f'  NULLed bad county "{r["county"]}": {n} records')

db.commit()
print(f'  Total bad counties NULLed: {bad_cty}')

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n=== FINAL VERMONT STATE ===")
total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']
in_vt = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' 
    AND latitude BETWEEN 42.7 AND 45.1 AND longitude BETWEEN -73.5 AND -71.4
""").fetchone()['n']

print(f'Total VT: {total:,} | GPS: {gps:,} ({100*gps//total}%) | In bbox: {in_vt:,} ({100*in_vt//total}%)')

# Remaining odd cities
print('\n--- Remaining city issues ---')
odd_remaining = db.execute("""
    SELECT city, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US'
    AND city IN ('Istanbul','Matsuyama','Fukuoka','Tokushima','Takamatsu','Shimonoseki','Kochi')
    GROUP BY city
""").fetchall()
if odd_remaining:
    for r in odd_remaining:
        print(f'  STILL WRONG: {r["city"]}: {r["n"]}')
else:
    print('  ✅ All odd city names fixed!')

# County status
null_cty = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND (county IS NULL OR county='')").fetchone()['n']
print(f'\nNULL county: {null_cty:,}')

# Top cities
print('\n--- Top 10 Cities ---')
for r in db.execute("SELECT city, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY city ORDER BY n DESC LIMIT 10"):
    print(f'  {r["city"]}: {r["n"]:,}')

# Faith breakdown
print('\n--- Faith Breakdown ---')
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r["faith"]}: {r["n"]:,}')

db.close()
print("\n✅ Vermont cleanup complete!")

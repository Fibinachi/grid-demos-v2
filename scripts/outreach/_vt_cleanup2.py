"""
VERMONT CLEANUP ROUND 2 — Delete garbage records, fix remaining city names.
"""
import sqlite3, time
from collections import defaultdict

DB_PATH = 'churches.db'
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.execute("PRAGMA journal_mode=WAL")

# ============================================================
# PHASE 1: Delete non-church scraped content (Japanese-named records)
# ============================================================
print("=== PHASE 1: Delete non-church scraped content ===")

jp_cities = ['Fukuoka','Matsuyama','Shimonoseki','Takamatsu','Tokushima','Kochi']
placeholders = ','.join(['?']*len(jp_cities))

# Count before
count_before = db.execute(f"""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ({placeholders})
""", jp_cities).fetchone()['n']
print(f'  Records to delete: {count_before}')

# These are news articles, blog posts, events — not churches. Delete them.
db.execute(f"""
    DELETE FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ({placeholders})
""", jp_cities)
db.commit()
print(f'  Deleted {count_before} non-church records')

# ============================================================
# PHASE 2: Fix "Istanbul" city via better reverse geocode
# ============================================================
print("\n=== PHASE 2: Fix remaining 'Istanbul' records ===")

# Build a better coordinate→city map from ALL New England records
coord_to_city = {}
for r in db.execute("""
    SELECT city, latitude, longitude FROM churches 
    WHERE state IN ('VT','NH','MA','NY','ME','CT','RI') AND country='US'
    AND city IS NOT NULL AND city != ''
    AND city NOT IN ('Istanbul','Amchitka')
    AND latitude IS NOT NULL
"""):
    # Use multiple rounding levels
    try:
        lat, lon = float(r['latitude']), float(r['longitude'])
        for precision in [3, 2]:
            key = (round(lat, precision), round(lon, precision), precision)
            if key not in coord_to_city:
                coord_to_city[key] = r['city']
    except (ValueError, TypeError):
        pass

print(f'  Coordinate→city map: {len(coord_to_city):,} entries')

# Fix Istanbul
fixed = 0
istanbul = db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NOT NULL
""").fetchall()

updates = []
for r in istanbul:
    found = None
    try:
        lat, lon = float(r['latitude']), float(r['longitude'])
        for precision in [3, 2]:
            key = (round(lat, precision), round(lon, precision), precision)
            candidate = coord_to_city.get(key)
            if candidate and candidate != 'Istanbul':
                found = candidate
                break
    except (ValueError, TypeError):
        pass
    if found:
        updates.append((found, r['id']))
        fixed += 1

if updates:
    db.executemany("UPDATE churches SET city=? WHERE id=?", updates)
    db.commit()
print(f'  Fixed {fixed}/{len(istanbul)} Istanbul records')

# ============================================================
# PHASE 3: Fix "Amchitka" city via reverse geocode
# ============================================================
print("\n=== PHASE 3: Fix 'Amchitka' records ===")

amchitka = db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NOT NULL
""").fetchall()

updates_am = []
for r in amchitka:
    found = None
    try:
        lat, lon = float(r['latitude']), float(r['longitude'])
        for precision in [3, 2]:
            key = (round(lat, precision), round(lon, precision), precision)
            candidate = coord_to_city.get(key)
            if candidate and candidate != 'Amchitka':
                found = candidate
                break
    except (ValueError, TypeError):
        pass
    if found:
        updates_am.append((found, r['id']))

if updates_am:
    db.executemany("UPDATE churches SET city=? WHERE id=?", updates_am)
    db.commit()
print(f'  Fixed {len(updates_am)}/{len(amchitka)} Amchitka records')

# ============================================================
# PHASE 4: Fix any Istanbul records still without GPS
# ============================================================
print("\n=== PHASE 4: Handle Istanbul records without GPS ===")

no_gps_istanbul = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NULL
""").fetchone()['n']

if no_gps_istanbul > 0:
    # These can't be fixed — NULL out the city
    db.execute("""
        UPDATE churches SET city=NULL 
        WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NULL
    """)
    db.commit()
    print(f'  NULLed city for {no_gps_istanbul} Istanbul records without GPS')

# ============================================================
# PHASE 5: Fix remaining Amchitka
# ============================================================
remaining_am = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka'
""").fetchone()['n']
if remaining_am > 0:
    # Use a broader approach — try to find nearest city by name pattern
    am_records = db.execute("""
        SELECT id, name FROM churches 
        WHERE state='VT' AND country='US' AND city='Amchitka'
    """).fetchall()
    
    # For those unfixed, try name-based extraction
    import re
    vt_towns_upper = {'ARLINGTON','BENNINGTON','BRATTLEBORO','BURLINGTON','COLCHESTER','ESSEX','FRANKLIN',
        'HARTFORD','LEICESTER','MIDDLEBURY','MONTPELIER','MORRISVILLE','NEWPORT','NORWICH',
        'RANDOLPH','READSBORO','RUTLAND','SAINT ALBANS','ST ALBANS','ST JOHNSBURY',
        'SHELBURNE','SPRINGFIELD','STOWE','SWANTON','WATERBURY','WILLISTON','WINOOSKI','WOODSTOCK',
        'BARRE','BELLOWS FALLS','BRANDON','BRISTOL','CASTLETON','CHARLOTTE','CHELSEA','CHESTER',
        'DANVILLE','DORSET','ENOSBURG','FAIRFAX','GEORGIA','GRAND ISLE','GREENSBORO','HARDWICK',
        'HIGHGATE','HINESBURG','HYDE PARK','JERICHO','JOHNSON','LUDLOW','LYNDONVILLE','MANCHESTER',
        'MIDDLESEX','MILTON','MORETOWN','NORTHFIELD','PITTSFORD','POULTNEY','PROCTOR','PUTNEY',
        'RICHFORD','RICHMOND','ROCKINGHAM','ROYALTON','SHARON','SHELDON','SOUTH BURLINGTON',
        'STARKSBORO','STRAFFORD','THETFORD','TOPSHAM','TOWNSHEND','TUNBRIDGE','UNDERHILL',
        'VERGENNES','WALLINGFORD','WARDSBORO','WATERFORD','WEATHERSFIELD','WELLS','WESTMINSTER',
        'WILMINGTON','WINDSOR','WOLCOTT','PROCTORSVILLE','JAMAICA'}
    
    name_updates = []
    for r in am_records:
        name_upper = r['name'].upper() if r['name'] else ''
        for town in sorted(vt_towns_upper, key=len, reverse=True):
            if town in name_upper:
                name_updates.append((town.title(), r['id']))
                break
    
    if name_updates:
        db.executemany("UPDATE churches SET city=? WHERE id=?", name_updates)
        db.commit()
        print(f'  Name-based fixes for Amchitka: {len(name_updates)}')
    
    remaining_am = db.execute("""
        SELECT COUNT(*) as n FROM churches 
        WHERE state='VT' AND country='US' AND city='Amchitka'
    """).fetchone()['n']
    print(f'  Remaining Amchitka after name fix: {remaining_am}')

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "="*60)
print("FINAL VERMONT SUMMARY")
print("="*60)

total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']
in_vt = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' 
    AND latitude BETWEEN 42.7 AND 45.1 AND longitude BETWEEN -73.5 AND -71.4
""").fetchone()['n']

print(f'Total VT churches: {total:,}')
print(f'GPS coverage: {gps:,} ({100*gps//total}%)')
print(f'In VT bounding box: {in_vt:,} ({100*in_vt//total}%)')

# Faith
print('\nFaith Breakdown:')
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r["faith"]}: {r["n"]:,}')

# Top cities
print('\nTop 15 Cities:')
for r in db.execute("SELECT city, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY city ORDER BY n DESC LIMIT 15"):
    print(f'  {r["city"]}: {r["n"]:,}')

# Tradition
print('\nTop 15 Traditions:')
for r in db.execute("""
    SELECT tradition, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND tradition IS NOT NULL 
    GROUP BY tradition ORDER BY n DESC LIMIT 15
"""):
    print(f'  {r["tradition"]}: {r["n"]:,}')

# Contact coverage
print('\nContact Coverage:')
for r in db.execute('''
    SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US'
    GROUP BY contact_type
'''):
    print(f'  {r["contact_type"]}: {r["n"]:,}')

# County coverage
print('\nCounty Status:')
good_cty = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND county IS NOT NULL AND county != ''
""").fetchone()['n']
null_cty = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND (county IS NULL OR county='')
""").fetchone()['n']
print(f'  With county: {good_cty:,} | NULL: {null_cty:,}')

# Check remaining garbage cities
odd = ['Istanbul','Amchitka','Fukuoka','Matsuyama','Shimonoseki','Takamatsu','Tokushima','Kochi']
odd_rem = db.execute(f"""
    SELECT city, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city IN ({','.join(['?']*len(odd))})
    GROUP BY city
""", odd).fetchall()
if odd_rem:
    print(f'\n⚠ Remaining odd cities: {len(odd_rem)} types')
    for r in odd_rem:
        print(f'  {r["city"]}: {r["n"]}')
else:
    print('\n✅ ALL odd city names cleaned!')

db.close()
print("\n✅ Vermont cleanup ROUND 2 complete!")

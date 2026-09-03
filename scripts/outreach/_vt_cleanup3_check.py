"""
VERMONT CLEANUP ROUND 3 — Fix remaining odd cities.
"""
import sqlite3

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# 1. Check Kōchi and Kitakyūshū - are they garbage too?
print("=== Kōchi / Kitakyūshū RECORDS ===")
for city in ['Kōchi', 'Kitakyūshū']:
    count = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city=?", [city]).fetchone()['n']
    print(f'\n{city}: {count} records')
    for r in db.execute("SELECT id, name, latitude, longitude, source, landmark_type FROM churches WHERE state='VT' AND country='US' AND city=? LIMIT 5", [city]):
        print(f'  "{r["name"][:70]}" | src={r["source"]} | gps=({r["latitude"]}, {r["longitude"]}) | type={r["landmark_type"]}')

# 2. Check remaining Amchitka - do they have GPS?
print("\n=== REMAINING AMCHITKA ===")
for r in db.execute("""
    SELECT id, name, latitude, longitude, source FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka'
    LIMIT 5
"""):
    print(f'  id={r["id"]} gps=({r["latitude"]}, {r["longitude"]}) "{r["name"][:60]}" src={r["source"]}')

# Count with/without GPS
with_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NOT NULL").fetchone()['n']
no_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NULL").fetchone()['n']
print(f'  With GPS: {with_gps}, Without GPS: {no_gps}')

# 3. Check remaining Istanbul
print("\n=== REMAINING ISTANBUL ===")
for r in db.execute("""
    SELECT id, name, latitude, longitude, source FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul'
    LIMIT 5
"""):
    print(f'  id={r["id"]} gps=({r["latitude"]}, {r["longitude"]}) "{r["name"][:60]}" src={r["source"]}')

with_gps_i = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NOT NULL").fetchone()['n']
no_gps_i = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NULL").fetchone()['n']
print(f'  With GPS: {with_gps_i}, Without GPS: {no_gps_i}')

# 4. Check Proctorsville - is this legit?
print("\n=== PROCTORSVILLE CHECK ===")
for r in db.execute("""
    SELECT name, city, latitude, longitude, source FROM churches 
    WHERE state='VT' AND country='US' AND city='Proctorsville'
    LIMIT 3
"""):
    in_vt = False
    try:
        lat, lon = float(r['latitude']), float(r['longitude'])
        in_vt = 42.7 <= lat <= 45.1 and -73.5 <= lon <= -71.4
    except: pass
    print(f'  {"IN_VT" if in_vt else "OUTSIDE"} "{r["name"][:60]}" @ ({r["latitude"]}, {r["longitude"]})')

db.close()

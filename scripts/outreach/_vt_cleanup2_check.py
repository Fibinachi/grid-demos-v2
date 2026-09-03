"""Vermont cleanup ROUND 2 — fix remaining issues."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# 1. Check unfixed Japanese-named records — are they real churches?
print("=== UNFIXED JAPANESE CITY RECORDS ===")
jp_cities = ['Fukuoka','Matsuyama','Shimonoseki','Takamatsu','Tokushima']
for r in db.execute(f"""
    SELECT id, name, city, latitude, longitude, landmark_type, source
    FROM churches WHERE state='VT' AND country='US' 
    AND city IN ({','.join(['?']*len(jp_cities))})
    LIMIT 10
""", jp_cities):
    print(f'  {r["city"]}: "{r["name"][:80]}" | src={r["source"]} | gps=({r["latitude"]}, {r["longitude"]}) | type={r["landmark_type"]}')

# 2. Check remaining Istanbul records
print("\n=== REMAINING ISTANBUL RECORDS ===")
for r in db.execute("""
    SELECT id, name, city, latitude, longitude, source
    FROM churches WHERE state='VT' AND country='US' AND city='Istanbul'
    LIMIT 10
"""):
    print(f'  id={r["id"]} "{r["name"][:60]}" | src={r["source"]} | ({r["latitude"]}, {r["longitude"]})')

# 3. Check Amchitka
print("\n=== AMCHITKA RECORDS ===")
for r in db.execute("""
    SELECT name, city, latitude, longitude, source, COUNT(*) as n
    FROM churches WHERE state='VT' AND country='US' AND city='Amchitka'
    LIMIT 5
"""):
    print(f'  ({r["latitude"]}, {r["longitude"]}) src={r["source"]} n={r["n"]}')

# Count of Amchitka with GPS vs without
am_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NOT NULL").fetchone()['n']
am_nogps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NULL").fetchone()['n']
print(f'  With GPS: {am_gps}, Without GPS: {am_nogps}')

# Check a few Amchitka coords
for r in db.execute("""
    SELECT name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka' AND latitude IS NOT NULL
    LIMIT 5
"""):
    in_vt = 42.7 <= r['latitude'] <= 45.1 and -73.5 <= r['longitude'] <= -71.4
    print(f'  {"IN_VT" if in_vt else "OUTSIDE"} "{r["name"][:60]}" @ ({r["latitude"]}, {r["longitude"]})')

# 4. Unfixed Istanbul — try broader reverse geocode
print("\n=== UNFIXED ISTANBUL — DETAIL ===")
for r in db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul' AND latitude IS NOT NULL
    LIMIT 5
"""):
    print(f'  ({r["latitude"]}, {r["longitude"]}) "{r["name"][:60]}"')

db.close()

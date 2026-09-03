"""Check what the Japanese-named VT records actually are."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Check the Japanese city records
print('=== JAPANESE CITY RECORDS IN VT ===')
odd = ['Matsuyama','Fukuoka','Tokushima','Takamatsu','Shimonoseki']
for city in odd:
    print(f'\n--- {city} (sample of 3) ---')
    for r in db.execute("""
        SELECT id, name, city, state, country, source, latitude, longitude, landmark_type, tradition
        FROM churches WHERE state='VT' AND country='US' AND city=?
        LIMIT 3
    """, [city]):
        print(f'  id={r["id"]} | {r["name"][:60]} | src={r["source"]} | type={r["landmark_type"]} | trad={r["tradition"]} | gps=({r["latitude"]}, {r["longitude"]})')

# Check if these IDs exist in any Japanese import
print('\n=== CHECKING IF THESE ARE JAPAN RECORDS ===')
jp_count = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='JP'").fetchone()['n']
print(f'Japan records total: {jp_count:,}')

# Check "Istanbul" records source
print('\n=== ISTANBUL RECORD SOURCES ===')
for r in db.execute("""
    SELECT source, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul'
    GROUP BY source ORDER BY n DESC
"""):
    print(f'  {r["source"]}: {r["n"]:,}')

# How many VT records are actually in VT by coordinates?
print('\n=== COORDINATE-BASED STATE CHECK ===')
# Check records with coords in VT bounding box but wrong state
for r in db.execute("""
    SELECT state, COUNT(*) as n
    FROM churches WHERE country='US'
    AND latitude BETWEEN 42.7 AND 45.1 
    AND longitude BETWEEN -73.5 AND -71.4
    GROUP BY state ORDER BY n DESC
"""):
    print(f'  {r["state"]}: {r["n"]:,}')

db.close()

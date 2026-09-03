"""Vermont church data quality check."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Check top VT cities - verify they're actually in Vermont
print('=== VT Records with unusual cities ===')
for r in db.execute("""
    SELECT name, city, state, country, latitude, longitude, landmark_type, tradition
    FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ('Matsuyama','Istanbul','Fukuoka','Tokushima','Takamatsu','Kochi','Shimonoseki')
    LIMIT 10
"""):
    print(f'  {r["city"]}: {r["name"][:60]} | {r["tradition"]} | ({r["latitude"]}, {r["longitude"]})')

# Check for legit VT cities
print('\n=== Legit VT city sample ===')
for r in db.execute("""
    SELECT name, city, tradition, latitude, longitude
    FROM churches 
    WHERE state='VT' AND country='US' 
    AND city IN ('Burlington','Rutland','Brattleboro','Barre','Montpelier','Bennington','Stowe','Middlebury')
    LIMIT 4
"""):
    print(f'  {r["city"]}: {r["name"][:60]} | {r["tradition"]} | ({r["latitude"]}, {r["longitude"]})')

# Count how many VT records have plausible Vermont-looking coordinates (lat 42.7-45, lon -73.4 to -71.5)
print('\n=== Coordinate validation ===')
total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
in_vt = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' 
    AND latitude BETWEEN 42.7 AND 45.1 
    AND longitude BETWEEN -73.5 AND -71.4
""").fetchone()['n']
print(f'Total VT: {total:,} | In VT bounding box: {in_vt:,} ({100*in_vt//total}%)')

# US totals for comparison
print('\n=== US TOTALS (for pitch context) ===')
us_total = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
us_gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND latitude IS NOT NULL").fetchone()['n']
us_phone = db.execute("""
    SELECT COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.country='US' AND cv.contact_type='phone'
""").fetchone()['n']
us_email = db.execute("""
    SELECT COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.country='US' AND cv.contact_type='email'
""").fetchone()['n']
us_web = db.execute("""
    SELECT COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.country='US' AND cv.contact_type='website'
""").fetchone()['n']
print(f'US total: {us_total:,} | GPS: {us_gps:,} ({100*us_gps//us_total}%)')
print(f'US with phone: {us_phone:,} | email: {us_email:,} | website: {us_web:,}')

# Faith breakdown US
print('\n--- US Faith Breakdown ---')
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE country='US' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r["faith"]}: {r["n"]:,}')

db.close()

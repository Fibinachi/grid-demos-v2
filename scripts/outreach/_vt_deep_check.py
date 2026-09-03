"""Deep Vermont data quality analysis before cleanup."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# 1. City name problems
print('=== CITY NAME ISSUES ===')
# What cities are in VT but don't belong?
for r in db.execute("""
    SELECT city, COUNT(*) as n, 
           AVG(latitude) as avg_lat, AVG(longitude) as avg_lon
    FROM churches 
    WHERE state='VT' AND country='US'
    GROUP BY city 
    HAVING AVG(latitude) NOT BETWEEN 42.7 AND 45.1 
        OR AVG(longitude) NOT BETWEEN -73.5 AND -71.4
    ORDER BY n DESC LIMIT 20
"""):
    print(f'  {r["city"]}: {r["n"]:,} @ ({r["avg_lat"]:.2f}, {r["avg_lon"]:.2f})')

# 2. Records outside VT bounding box
print('\n=== RECORDS OUTSIDE VT BOUNDING BOX ===')
for r in db.execute("""
    SELECT city, COUNT(*) as n, 
           ROUND(AVG(latitude),2) as avg_lat, ROUND(AVG(longitude),2) as avg_lon
    FROM churches 
    WHERE state='VT' AND country='US'
    AND (latitude NOT BETWEEN 42.7 AND 45.1 OR longitude NOT BETWEEN -73.5 AND -71.4)
    GROUP BY city ORDER BY n DESC LIMIT 15
"""):
    print(f'  {r["city"]}: {r["n"]:,} @ ({r["avg_lat"]}, {r["avg_lon"]})')

# 3. What's the source distribution for VT?
print('\n=== SOURCE DISTRIBUTION ===')
for r in db.execute("""
    SELECT source, COUNT(*) as n 
    FROM churches 
    WHERE state='VT' AND country='US'
    GROUP BY source ORDER BY n DESC
"""):
    print(f'  {r["source"]}: {r["n"]:,}')

# 4. Check if there are records with VT coordinates but wrong state
print('\n=== ACTUALLY-IN-VT RECORDS WITH WRONG STATE ===')
for r in db.execute("""
    SELECT state, COUNT(*) as n
    FROM churches 
    WHERE country='US'
    AND latitude BETWEEN 42.7 AND 45.1 
    AND longitude BETWEEN -73.5 AND -71.4
    AND state != 'VT'
    GROUP BY state ORDER BY n DESC LIMIT 10
"""):
    print(f'  state={r["state"]}: {r["n"]:,}')

# 5. Check the "Istanbul" records - are coords in VT?
print('\n=== ISTANBUL RECORDS - COORDINATE CHECK ===')
for r in db.execute("""
    SELECT name, latitude, longitude, 
           CASE WHEN latitude BETWEEN 42.7 AND 45.1 AND longitude BETWEEN -73.5 AND -71.4 
                THEN 'IN_VT' ELSE 'OUTSIDE' END as location
    FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul'
    LIMIT 5
"""):
    print(f'  {r["location"]}: {r["name"][:60]} @ ({r["latitude"]}, {r["longitude"]})')

# 6. Japanese city check
print('\n=== JAPANESE/ODD CITY RECORDS ===')
odd_cities = ['Matsuyama','Fukuoka','Tokushima','Takamatsu','Kochi','Shimonoseki']
placeholders = ','.join(['?']*len(odd_cities))
for r in db.execute(f"""
    SELECT city, COUNT(*) as n,
           ROUND(AVG(latitude),2) as avg_lat, ROUND(AVG(longitude),2) as avg_lon
    FROM churches 
    WHERE state='VT' AND country='US' AND city IN ({placeholders})
    GROUP BY city ORDER BY n DESC
""", odd_cities):
    print(f'  {r["city"]}: {r["n"]:,} @ ({r["avg_lat"]}, {r["avg_lon"]})')

# 7. County issues - how many VT records have non-VT counties?
vt_counties = {'Addison','Bennington','Caledonia','Chittenden','Essex','Franklin',
               'Grand Isle','Lamoille','Orange','Orleans','Rutland','Washington','Windham','Windsor'}
print('\n=== COUNTY ISSUES ===')
non_vt = db.execute(f"""
    SELECT county, COUNT(*) as n 
    FROM churches WHERE state='VT' AND country='US' 
    AND county IS NOT NULL AND county != ''
    AND county NOT IN ({','.join(['?']*len(vt_counties))})
    GROUP BY county ORDER BY n DESC
""", list(vt_counties)).fetchall()
for r in non_vt[:15]:
    print(f'  {r["county"]}: {r["n"]:,}')

null_cty = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND (county IS NULL OR county='')").fetchone()
print(f'  NULL/empty county: {null_cty["n"]:,}')

db.close()

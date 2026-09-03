"""Detailed analysis of JW hierarchy patterns with geo data."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
c = db.cursor()

print('=== ALL CONGREGATION PATTERNS ===')
rows = c.execute("""
    SELECT name, COUNT(*),
           MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city END) as sample_city,
           MAX(country) as country
    FROM churches
    WHERE (name LIKE '%Congregation%' OR name LIKE '%congregation%')
    AND (name LIKE '%Jehov%' OR name LIKE '%Witness%' OR name LIKE '%Wtnss%')
    GROUP BY name ORDER BY COUNT(*) DESC
""").fetchall()
for name, cnt, city, cc in rows:
    city_s = city or '-'
    print(f'  [{cnt:2d}] {name[:100]:100s}  city={city_s:20s}  {cc}')

print()
print('=== ASSEMBLY HALL WITH CITY ===')
rows = c.execute("""
    SELECT name, COUNT(*),
           MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city END) as sample_city,
           MAX(country)
    FROM churches
    WHERE (name LIKE '%Assembly%Hall%' OR name LIKE '%Assembly Hall%')
    AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')
    AND city IS NOT NULL AND city != '' AND city != 'None'
    GROUP BY name ORDER BY COUNT(*) DESC
""").fetchall()
for name, cnt, city, cc in rows:
    print(f'  [{cnt:2d}] {name[:100]:100s}  city={city:20s}  {cc}')

print()
print('=== ASSEMBLY HALL WITHOUT CITY ===')
rows = c.execute("""
    SELECT name, COUNT(*), MAX(country)
    FROM churches
    WHERE (name LIKE '%Assembly%Hall%' OR name LIKE '%Assembly Hall%')
    AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')
    AND (city IS NULL OR city = '' OR city = 'None')
    GROUP BY name ORDER BY COUNT(*) DESC
""").fetchall()
for name, cnt, cc in rows:
    print(f'  [{cnt:2d}] {name[:100]:100s}  country={cc}')

print()
print('=== CIRCUITS ===')
rows = c.execute("""
    SELECT name, COUNT(*),
           MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city END),
           MAX(country)
    FROM churches WHERE name LIKE '%Circuit%'
    AND (name LIKE '%Jehov%' OR name LIKE '%Witness%')
    GROUP BY name ORDER BY name
""").fetchall()
for name, cnt, city, cc in rows:
    city_s = city or '-'
    print(f'  [{cnt}] {name:70s}  city={city_s:20s}  {cc}')

print()
print('=== KINGDOM HALL NAME-SUFFIX CITIES (for congregation linking) ===')
rows = c.execute("""
    SELECT name, COUNT(*),
           MAX(CASE WHEN city IS NOT NULL AND city != '' AND city != 'None' THEN city END) as sample_city
    FROM churches
    WHERE name LIKE '%Kingdom Hall%'
    AND name LIKE '%\u2014%'  -- em dash separator
    AND (city IS NOT NULL AND city != '' AND city != 'None')
    GROUP BY name ORDER BY COUNT(*) DESC
    LIMIT 30
""").fetchall()
for name, cnt, city in rows:
    print(f'  [{cnt:2d}] {name[:100]:100s}  city={city:20s}')

db.close()

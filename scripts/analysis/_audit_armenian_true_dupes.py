"""Find true Armenian duplicates — matching same name+city or same coords."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=== TRUE DUPLICATES: same name + same city ===")
rows = db.execute("""
    SELECT name, country, city, 
           COUNT(*) as cnt,
           MAX(latitude) as max_lat, MIN(latitude) as min_lat,
           MAX(longitude) as max_lon, MIN(longitude) as min_lon,
           GROUP_CONCAT(DISTINCT source) as sources,
           GROUP_CONCAT(DISTINCT state) as states
    FROM churches 
    WHERE (name LIKE '%Armenian%' OR name LIKE '%armenian%')
      AND city IS NOT NULL AND city != ''
    GROUP BY name, country, city 
    HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"Groups: {len(rows)}")
total_dup = sum(r['cnt'] for r in rows)
print(f"Records in groups: {total_dup}")
print(f"Would delete: {total_dup - len(rows)}\n")

for r in rows[:50]:
    lat_range = abs((r['max_lat'] or 0) - (r['min_lat'] or 0))
    lon_range = abs((r['max_lon'] or 0) - (r['min_lon'] or 0))
    print(f"  [{r['cnt']}x] {r['name']}")
    print(f"        {r['city']}, {r['states']} | {r['country']}")
    print(f"        sources={r['sources']}")
    print(f"        coord_range: {lat_range:.6f} x {lon_range:.6f}\n")

print("\n=== SAME COORDS (lat/lon within 0.0001) ===")
rows2 = db.execute("""
    SELECT a.name, a.country, a.city, a.state, 
           a.rowid as id1, b.rowid as id2,
           a.latitude, a.longitude, a.source as src1, b.source as src2
    FROM churches a
    JOIN churches b ON a.name = b.name AND a.country = b.country
    WHERE (a.name LIKE '%Armenian%' OR a.name LIKE '%armenian%')
      AND a.rowid < b.rowid
      AND a.latitude IS NOT NULL AND b.latitude IS NOT NULL
      AND ABS(a.latitude - b.latitude) < 0.0001
      AND ABS(a.longitude - b.longitude) < 0.0001
    ORDER BY a.name
""").fetchall()

print(f"Pairs: {len(rows2)}")
for r in rows2:
    print(f"  {r['name']} | {r['city']}, {r['state']} | {r['country']}")
    print(f"    rowid={r['id1']} src={r['src1']} vs rowid={r['id2']} src={r['src2']}")
    coord_str = f"({r['latitude']}, {r['longitude']})"
    print(f"    coord {coord_str}\n")

# Also check for dupes where one city has trailing spaces / case differences
print("\n=== SAME NAME + SAME COORDS (city-agnostic) ===")
rows3 = db.execute("""
    SELECT a.name, a.country,
           a.rowid as id1, b.rowid as id2,
           a.city as city1, b.city as city2,
           a.state as state1, b.state as state2,
           a.source as src1, b.source as src2,
           a.latitude, a.longitude
    FROM churches a
    JOIN churches b ON a.name = b.name AND a.country = b.country
    WHERE (a.name LIKE '%Armenian%' OR a.name LIKE '%armenian%')
      AND a.rowid < b.rowid
      AND a.latitude IS NOT NULL AND b.latitude IS NOT NULL
      AND ABS(a.latitude - b.latitude) < 0.001
      AND ABS(a.longitude - b.longitude) < 0.001
      AND (a.city IS NULL OR b.city IS NULL OR UPPER(TRIM(a.city)) != UPPER(TRIM(b.city)))
    ORDER BY a.name
""").fetchall()

print(f"Cross-city same-coord pairs: {len(rows3)}")
for r in rows3:
    print(f"  {r['name']} | {r['country']}")
    print(f"    rowid={r['id1']} city={r['city1']} state={r['state1']} src={r['src1']}")
    print(f"    rowid={r['id2']} city={r['city2']} state={r['state2']} src={r['src2']}")
    print(f"    coord=({r['latitude']}, {r['longitude']})\n")

db.close()

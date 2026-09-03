"""Analyze Judaism entries that share locations (same building, different congregations)."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# 1. Entries sharing exact GPS coordinates
print("=== Entries sharing exact GPS coordinates ===")
c.execute("""
    SELECT ROUND(latitude, 5), ROUND(longitude, 5), COUNT(*) as cnt,
           GROUP_CONCAT(SUBSTR(name, 1, 60), '|') as names,
           GROUP_CONCAT(city, '|') as cities,
           GROUP_CONCAT(state, '|') as states,
           GROUP_CONCAT(country, '|') as countries,
           GROUP_CONCAT(landmark_type, '|') as types,
           GROUP_CONCAT(tradition, '|') as traditions
    FROM churches
    WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude, 5), ROUND(longitude, 5)
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 100
""")
rows = c.fetchall()
print(f"Total location-sharing groups (same GPS): {len(rows)}")
total_shared_gps = sum(r[2] for r in rows)
print(f"Total entries in shared locations: {total_shared_gps}")

print(f"\nTop 20 shared-location groups:")
for r in rows[:20]:
    lat, lon, cnt, names, cities, states, countries, types, traditions = r
    nlist = names.split('|')
    city_list = cities.split('|')
    type_list = types.split('|')
    trad_list = traditions.split('|')
    unique_types = set(type_list)
    unique_trads = set(trad_list)
    print(f"\n  {cnt} entries at ({lat}, {lon})")
    print(f"  Cities: {set(cities.split('|'))}, Countries: {set(countries.split('|'))}")
    print(f"  Types: {unique_types}  Traditions: {unique_trads}")
    for i in range(min(cnt, len(nlist))):
        print(f"    {nlist[i].strip():45s} {city_list[i]:20s} {type_list[i]:15s} {trad_list[i]}")

# 2. Count total unique vs shared
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL")
with_gps = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT ROUND(latitude,5)||','||ROUND(longitude,5)) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL")
unique_locations = c.fetchone()[0]

print(f"\n\n=== Summary ===")
print(f"Total Judaism entries with GPS: {with_gps:,}")
print(f"Unique GPS locations: {unique_locations:,}")
print(f"Entries sharing a location: {total_shared_gps:,}")
print(f"Groups of shared locations: {len(rows):,}")
print(f"Potential extra congregations: {total_shared_gps - len(rows):,}")

# 3. Same street address
print(f"\n\n=== Entries sharing street address ===")
c.execute("""
    SELECT city, state, country, address, COUNT(*) as cnt,
           GROUP_CONCAT(SUBSTR(name, 1, 60), '|') as names,
           GROUP_CONCAT(landmark_type, '|') as types
    FROM churches
    WHERE faith='Judaism' AND address IS NOT NULL AND address != ''
    GROUP BY city, state, country, address
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 50
""")
rows2 = c.fetchall()
print(f"Groups sharing same address: {len(rows2)}")
for r in rows2[:10]:
    city, state, country, addr, cnt, names, types = r
    print(f"\n  {cnt} entries at {addr}, {city}, {state}, {country}")
    nlist = names.split('|')
    tlist = types.split('|')
    for i in range(cnt):
        print(f"    {nlist[i].strip():45s} type={tlist[i]}")

# 4. Type breakdown in shared locations
print(f"\n\n=== Type breakdown in shared locations ===")
c.execute("""
    WITH dups AS (
        SELECT ROUND(latitude, 5) as rlat, ROUND(longitude, 5) as rlon
        FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY rlat, rlon HAVING COUNT(*) > 1
    )
    SELECT c.landmark_type, COUNT(*) as cnt
    FROM churches c
    JOIN dups d ON ROUND(c.latitude,5)=d.rlat AND ROUND(c.longitude,5)=d.rlon
    WHERE c.faith='Judaism'
    GROUP BY c.landmark_type
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>6,}")

# 5. Multiple synagogues at same spot
print(f"\n\n=== Locations with multiple 'synagogue' entries ===")
c.execute("""
    WITH dups AS (
        SELECT ROUND(latitude, 5) as rlat, ROUND(longitude, 5) as rlon
        FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY rlat, rlon HAVING COUNT(*) > 1
    )
    SELECT d.rlat, d.rlon, COUNT(*) as cnt,
           GROUP_CONCAT(SUBSTR(c.name, 1, 50), '|') as names,
           GROUP_CONCAT(c.tradition, '|') as traditions
    FROM churches c
    JOIN dups d ON ROUND(c.latitude,5)=d.rlat AND ROUND(c.longitude,5)=d.rlon
    WHERE c.faith='Judaism' AND c.landmark_type = 'synagogue'
    GROUP BY d.rlat, d.rlon
    HAVING cnt > 1
    ORDER BY cnt DESC
""")
multi_syn = c.fetchall()
print(f"Locations with multiple 'synagogue' entries: {len(multi_syn)}")
for r in multi_syn[:15]:
    print(f"\n  {r[2]} synagogues at ({r[0]}, {r[1]}):")
    nlist = r[3].split(',')
    tlist = r[4].split(',')
    for i in range(r[2]):
        print(f"    {nlist[i].strip():45s} {tlist[i]}")

conn.close()

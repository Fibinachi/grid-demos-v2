"""
Audit China religious sites coverage:
1. What Overture landmarks exist for CN that we haven't imported?
2. What does our current CN data look like by source/type?
3. What's the estimated gap?
"""
import sqlite3

DB = 'E:/grid/churches.db'
conn = sqlite3.connect(DB)
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()

print("=" * 60)
print("CHINA (CN) RELIGIOUS SITES - COVERAGE AUDIT")
print("=" * 60)

# 1. Current state
c.execute("SELECT COUNT(*) FROM churches WHERE country='CN'")
print(f"\nTotal CN records: {c.fetchone()[0]:,}")

# By source_primary
c.execute("""SELECT COUNT(*), source_primary, source_secondary 
FROM churches WHERE country='CN' 
GROUP BY source_primary, source_secondary 
ORDER BY COUNT(*) DESC""")
print("\nBy source:")
for cnt, sp, ss in c.fetchall():
    print(f"  {sp} / {ss}: {cnt:,}")

# By landmark_type
c.execute("""SELECT COUNT(*), landmark_type 
FROM churches WHERE country='CN' 
GROUP BY landmark_type ORDER BY COUNT(*) DESC""")
print("\nBy landmark_type:")
for cnt, lt in c.fetchall():
    print(f"  {lt}: {cnt:,}")

# 2. How many have overture_id vs wikidata_qid?
c.execute("""SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN overture_id IS NOT NULL AND overture_id != '' THEN 1 ELSE 0 END) as has_overture,
    SUM(CASE WHEN wikidata_qid IS NOT NULL AND wikidata_qid != '' THEN 1 ELSE 0 END) as has_wikidata,
    SUM(CASE WHEN holy_site_id IS NOT NULL THEN 1 ELSE 0 END) as has_holy_site
FROM churches WHERE country='CN'""")
row = c.fetchone()
print(f"\nID coverage: overture={row[1]}, wikidata={row[2]}, holy_site={row[3]} / {row[0]}")

# 3. Check for CN entries with wrong country (e.g., Kowloon Mosque listed in CN but actually HK)
print("\n=== Potential country mis-assignments ===")
c.execute("""SELECT name, city, latitude, longitude FROM churches 
WHERE country='CN' AND (name LIKE '%Kowloon%' OR name LIKE '%Hong Kong%' OR name LIKE '%Macau%')""")
for row in c.fetchall():
    print(f"  {row[0]} | {row[1]} | ({row[2]},{row[3]})")

# 4. What faith values are null or generic?
c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND (faith IS NULL OR faith = '')")
print(f"\nNull/empty faith: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND (denomination IS NULL OR denomination = '')")
print(f"Null/empty denomination: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND (city IS NULL OR city = '')")
print(f"Null/empty city: {c.fetchone()[0]:,}")

# 5. Check province/state coverage 
c.execute("SELECT COUNT(*), state FROM churches WHERE country='CN' AND state IS NOT NULL GROUP BY state ORDER BY COUNT(*) DESC LIMIT 10")
print("\nBy state (top 10):")
for cnt, st in c.fetchall():
    print(f"  {st}: {cnt:,}")

# 6. What provinces are most represented by lat/lon clustering?
print("\n=== Provincial distribution (by lat/lon approximation) ===")
# Rough provinces by lat/lon bounding boxes
provinces = {
    "Xinjiang": (35, 49, 73, 97),
    "Tibet": (26, 37, 78, 100),
    "Inner Mongolia": (37, 54, 97, 127),
    "Heilongjiang": (43, 54, 121, 136),
    "Yunnan": (21, 30, 97, 107),
    "Sichuan": (26, 35, 97, 109),
    "Gansu": (32, 43, 92, 109),
    "Qinghai": (31, 40, 89, 104),
    "Beijing": (39, 41, 115, 118),
    "Shanghai": (30, 32, 120, 122),
    "Guangdong": (20, 26, 109, 118),
    "Fujian": (23, 29, 115, 121),
    "Zhejiang": (27, 31, 118, 123),
    "Jiangsu": (30, 36, 116, 122),
    "Shandong": (34, 39, 114, 123),
    "Henan": (31, 37, 110, 117),
    "Hubei": (29, 34, 108, 117),
    "Hunan": (24, 31, 108, 115),
    "Guangxi": (21, 27, 104, 113),
    "Guizhou": (24, 30, 103, 110),
    "Shaanxi": (31, 40, 105, 112),
    "Shanxi": (34, 41, 110, 115),
    "Hebei": (36, 43, 113, 120),
    "Liaoning": (38, 44, 118, 126),
    "Jilin": (40, 47, 121, 132),
    "Anhui": (29, 35, 114, 120),
    "Jiangxi": (24, 31, 113, 119),
    "Hainan": (18, 21, 108, 111),
    "Ningxia": (35, 40, 104, 108),
    "Chongqing": (28, 33, 105, 111),
    "Tianjin": (38, 41, 116, 119),
}
for prov, (lat_min, lat_max, lon_min, lon_max) in provinces.items():
    c.execute("""SELECT COUNT(*) FROM churches WHERE country='CN' 
        AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?""",
        (lat_min, lat_max, lon_min, lon_max))
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  {prov}: {cnt}")

conn.close()

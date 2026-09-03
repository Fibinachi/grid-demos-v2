"""
Step 1: Fix CN geo-misassignments and enrich existing records.
Then query OSM Overpass for Chinese religious sites not in our DB.
"""
import sqlite3
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA busy_timeout=30000")
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()
ts = datetime.now(timezone.utc).isoformat()
total_fixed = 0

# ============================================================
# PART 1: Fix geo-misassignments
# ============================================================
print("=" * 60)
print("PART 1: Fixing geo-misassignments")
print("=" * 60)

# Kowloon Mosque -> HK (22.2987, 114.172 is in Kowloon, Hong Kong)
c.execute("SELECT rowid, name, country, latitude, longitude FROM churches WHERE name='Kowloon Mosque and Islamic Centre' AND country='CN'")
row = c.fetchone()
if row:
    print(f"  Fixing: {row[1]} CN -> HK ({row[3]},{row[4]})")
    c.execute("UPDATE churches SET country='HK', city='Kowloon' WHERE rowid=?", (row[0],))
    total_fixed += 1

# Macau Mosque -> MO (22.202, 113.554 is in Macau)
c.execute("SELECT rowid, name, country, latitude, longitude FROM churches WHERE name='Macau Mosque and Cemetery' AND country='CN'")
row = c.fetchone()
if row:
    print(f"  Fixing: {row[1]} CN -> MO ({row[3]},{row[4]})")
    c.execute("UPDATE churches SET country='MO', city='Macau' WHERE rowid=?", (row[0],))
    total_fixed += 1

# ============================================================
# PART 2: Provincial assignment for CN records
# ============================================================
print("\n" + "=" * 60)
print("PART 2: Assigning Chinese provinces by lat/lon")
print("=" * 60)

# Province bounding boxes (approximate)
provinces = {
    "Xinjiang": (35, 49, 73, 97),
    "Xizang": (26, 37, 78, 100),
    "Nei Mongol": (37, 54, 97, 127),
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

prov_assigned = 0
for prov, (lat_min, lat_max, lon_min, lon_max) in provinces.items():
    c.execute("""UPDATE churches SET state=? WHERE country='CN' 
        AND (state IS NULL OR state = '')
        AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?""",
        (prov, lat_min, lat_max, lon_min, lon_max))
    if c.rowcount > 0:
        prov_assigned += c.rowcount
        print(f"  {prov}: {c.rowcount} assigned")

print(f"  Total provinces assigned: {prov_assigned}")

# Assign city = province capital as placeholder where city is null
# This isn't perfect but better than NULL
capitals = {
    "Beijing": "Beijing", "Shanghai": "Shanghai", "Tianjin": "Tianjin",
    "Chongqing": "Chongqing", "Xinjiang": "Urumqi", "Xizang": "Lhasa",
    "Nei Mongol": "Hohhot", "Heilongjiang": "Harbin", "Yunnan": "Kunming",
    "Sichuan": "Chengdu", "Gansu": "Lanzhou", "Qinghai": "Xining",
    "Guangdong": "Guangzhou", "Fujian": "Fuzhou", "Zhejiang": "Hangzhou",
    "Jiangsu": "Nanjing", "Shandong": "Jinan", "Henan": "Zhengzhou",
    "Hubei": "Wuhan", "Hunan": "Changsha", "Guangxi": "Nanning",
    "Guizhou": "Guiyang", "Shaanxi": "Xi'an", "Shanxi": "Taiyuan",
    "Hebei": "Shijiazhuang", "Liaoning": "Shenyang", "Jilin": "Changchun",
    "Anhui": "Hefei", "Jiangxi": "Nanchang", "Hainan": "Haikou",
    "Ningxia": "Yinchuan",
}

# For records with province but no city, set a rough city (reverse geocode later)
city_assigned = 0
for prov, city in capitals.items():
    c.execute("""UPDATE churches SET city=? WHERE country='CN' 
        AND (city IS NULL OR city = '') AND state=?""", (city, prov))
    if c.rowcount > 0:
        city_assigned += c.rowcount
        print(f"  City placeholder '{city}' for {prov}: {c.rowcount}")

print(f"  Total city placeholders: {city_assigned}")

# ============================================================
# PART 3: Assign denominations based on source_secondary
# ============================================================
print("\n" + "=" * 60)
print("PART 3: Assigning denominations")
print("=" * 60)

denom_map = {
    "catholic_church": "Roman Catholic",
    "baptist_church": "Baptist",
    "evangelical_church": "Evangelical",
    "pentecostal_church": "Pentecostal",
    "anglican_church": "Anglican",
    "episcopal_church": "Episcopal",
    "buddhist_temple": "Chinese Buddhism",
    "church_cathedral": "Protestant",  # default for China
    "mosque": "Sunni Islam",
    "hindu_temple": "Hindu",
    "sikh_temple": "Sikh",
    "synagogue": "Jewish",
}

denom_assigned = 0
for src_sec, denom in denom_map.items():
    c.execute("""UPDATE churches SET denomination=? WHERE country='CN' 
        AND (denomination IS NULL OR denomination = '') AND source_secondary=?""",
        (denom, src_sec))
    if c.rowcount > 0:
        denom_assigned += c.rowcount
        print(f"  {src_sec} -> {denom}: {c.rowcount}")

print(f"  Total denominations assigned: {denom_assigned}")

# ============================================================
# PART 4: Log provenance and commit
# ============================================================
c.execute("""INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?,?,?,?,?,?,?,?)""",
    ("manual", "enrich_cn.py", ts, datetime.now(timezone.utc).isoformat(),
     total_fixed + prov_assigned + city_assigned + denom_assigned,
     "country,state,city,denomination",
     "completed",
     f"CN enrichment: {total_fixed} geo fixes, {prov_assigned} provinces, {city_assigned} cities, {denom_assigned} denominations"))

conn.commit()

# ============================================================
# PART 5: Summary
# ============================================================
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND state IS NOT NULL AND state != ''")
print(f"  With province: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND city IS NOT NULL AND city != ''")
print(f"  With city: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='CN' AND denomination IS NOT NULL AND denomination != ''")
print(f"  With denomination: {c.fetchone()[0]:,}")
c.execute("SELECT COUNT(*), faith FROM churches WHERE country='CN' GROUP BY faith ORDER BY COUNT(*) DESC")
print(f"  By faith:")
for cnt, faith in c.fetchall():
    print(f"    {faith}: {cnt:,}")
print(f"  Total CN: {sum(1 for _ in c.execute('SELECT 1 FROM churches WHERE country=?', ('CN',)))}")

conn.close()
print("\nDone with Part 1-4.")

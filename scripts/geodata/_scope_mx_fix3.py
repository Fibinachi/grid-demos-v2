"""Detail check on clearly-US MX records"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# osm_import MX north of 32°N — state distribution
c.execute("""
    SELECT 
        CASE WHEN state IS NULL OR state = '' OR state = 'None' THEN 'NULL'
             ELSE state END as state_val,
        COUNT(*) as cnt
    FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude >= 32
    AND longitude BETWEEN -125 AND -65
    GROUP BY state_val
    ORDER BY cnt DESC
""")
print("=== osm_import MX north of 32°N — state distribution ===")
for r in c.fetchall():
    print(f"  {str(r[0]):10s}  {r[1]:>7,}")

# Also check city distribution
c.execute("""
    SELECT 
        CASE WHEN city IS NULL OR city = '' OR city = 'None' THEN 'NULL'
             ELSE city END as city_val,
        COUNT(*) as cnt
    FROM churches 
    WHERE country='MX' AND source='osm_import'
    AND latitude >= 32
    AND longitude BETWEEN -125 AND -65
    GROUP BY city_val
    ORDER BY cnt DESC
    LIMIT 20
""")
print("\n=== osm_import MX north of 32°N — top cities ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:30]:30s}  {r[1]:>7,}")

# Same for holy_sites_import north of 32
c.execute("""
    SELECT 
        CASE WHEN state IS NULL OR state = '' OR state = 'None' THEN 'NULL'
             ELSE state END as state_val,
        COUNT(*) as cnt
    FROM churches 
    WHERE country='MX' AND source='holy_sites_import'
    AND latitude >= 32
    AND longitude BETWEEN -125 AND -65
    GROUP BY state_val
    ORDER BY cnt DESC
""")
print("\n=== holy_sites_import MX north of 32°N — state ===")
for r in c.fetchall():
    print(f"  {str(r[0]):10s}  {r[1]:>7,}")

# Check distinct lon distribution for osm_import north of 32
c.execute("""
    SELECT ROUND(longitude, -1) as lon_bin, COUNT(*) 
    FROM churches WHERE country='MX' AND source='osm_import'
    AND latitude >= 32 AND longitude BETWEEN -125 AND -65
    GROUP BY lon_bin ORDER BY lon_bin
""")
print("\n=== osm_import MX north of 32 — lon distribution ===")
for r in c.fetchall():
    print(f"  lon ~ {r[0]:4.0f}°  {r[1]:>7,}")

# Count total across all sources: MX records with lat>=32 (clearly US)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND latitude >= 32 AND longitude BETWEEN -125 AND -65
""")
all_north32 = c.fetchone()[0]
print(f"\nALL MX records north of 32°N: {all_north32:,}")

# By source
c.execute("""
    SELECT source, COUNT(*) FROM churches 
    WHERE country='MX' AND latitude >= 32 AND longitude BETWEEN -125 AND -65
    GROUP BY source ORDER BY COUNT(*) DESC
""")
print("=== By source ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:50]:50s}  {r[1]:>7,}")

db.close()

"""Check broader angles: denomination 'Mexican' in US + MX country records with OSM"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# Angle 1: Denomination contains 'Mexican' but country is US
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='US' 
    AND (denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%')
""")
mexican_denom_us = c.fetchone()[0]
print(f"US churches with 'Mexican' in denomination: {mexican_denom_us:,}")

# See the denominations
c.execute("""
    SELECT denomination, COUNT(*) FROM churches 
    WHERE country='US' 
    AND (denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%')
    GROUP BY denomination ORDER BY COUNT(*) DESC
""")
print("\n=== 'Mexican' denominations in US ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:60]:60s}  {r[1]:>6,}")

# Angle 2: MX country records — but what sources have the bulk?
c.execute("""
    SELECT source, COUNT(*) FROM churches 
    WHERE country='MX'
    GROUP BY source ORDER BY COUNT(*) DESC
""")
print("\n=== All MX records by source ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:40]:40s}  {r[1]:>8,}")

# Angle 3: osm_import MX records — do they have state=Nuevo Leon etc?
c.execute("""
    SELECT state, COUNT(*) FROM churches 
    WHERE country='MX' AND source LIKE 'osm_import%'
    GROUP BY state ORDER BY COUNT(*) DESC LIMIT 15
""")
print("\n=== osm_import MX records by state ===")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):20s}  {r[1]:>8,}")

# Angle 4: holy_sites_import MX records by state
c.execute("""
    SELECT state, COUNT(*) FROM churches 
    WHERE country='MX' AND source LIKE 'holy_sites_import%'
    GROUP BY state ORDER BY COUNT(*) DESC LIMIT 15
""")
print("\n=== holy_sites_import MX records by state ===")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):20s}  {r[1]:>8,}")

# Angle 5: Check how many osm_import MX records have NULL state 
c.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND source LIKE 'osm_import%' AND (state IS NULL OR state='' OR state='None')")
print(f"\nosm_import MX with NULL state: {c.fetchone()[0]:,}")

# Angle 6: holy_sites_import MX records with NULL state
c.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND source LIKE 'holy_sites_import%' AND (state IS NULL OR state='' OR state='None')")
print(f"holy_sites_import MX with NULL state: {c.fetchone()[0]:,}")

# Angle 7: osm_import MX — check if the city field has Mexican state names  
c.execute("""
    SELECT city, COUNT(*) FROM churches 
    WHERE country='MX' AND source LIKE 'osm_import%'
    AND city IS NOT NULL AND city != '' AND city != 'None'
    GROUP BY city ORDER BY COUNT(*) DESC LIMIT 20
""")
print("\n=== osm_import MX — top city values ===")
for r in c.fetchall():
    print(f"  {str(r[0] or '')[:30]:30s}  {r[1]:>8,}")

# Angle 8: holy_sites_import MX — top cities
c.execute("""
    SELECT city, COUNT(*) FROM churches 
    WHERE country='MX' AND source LIKE 'holy_sites_import%'
    AND city IS NOT NULL AND city != '' AND city != 'None'
    GROUP BY city ORDER BY COUNT(*) DESC LIMIT 20
""")
print("\n=== holy_sites_import MX — top city values ===")
for r in c.fetchall():
    print(f"  {str(r[0] or '')[:30]:30s}  {r[1]:>8,}")

# Angle 9: Check overture_mexico source
c.execute("SELECT COUNT(*) FROM churches WHERE source='overture_mexico'")
print(f"\n'overture_mexico' source records: {c.fetchone()[0]:,}")

# Angle 10: Maybe it's about overture records that are in MX but should be US?
# Overture has its own country assignment. Let's see.
c.execute("""
    SELECT country, COUNT(*) FROM churches 
    WHERE source LIKE 'overture%'
    GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10
""")
print("\n=== Overture records by country ===")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):15s}  {r[1]:>8,}")

db.close()

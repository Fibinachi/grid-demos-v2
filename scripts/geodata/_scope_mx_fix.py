"""Use county_fips_5 to find definitely-US MX records"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# MX records with county_fips_5 (from spatial join → definitely US)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
""")
fips_mx = c.fetchone()[0]
print(f"MX records with county_fips_5 (definitely US): {fips_mx:,}")

# Same but for osm_import specifically
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import' 
    AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
""")
osm_fips = c.fetchone()[0]
print(f"  osm_import MX with county_fips_5: {osm_fips:,}")

# For holy_sites_import
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='holy_sites_import' 
    AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
""")
holy_fips = c.fetchone()[0]
print(f"  holy_sites_import MX with county_fips_5: {holy_fips:,}")

# Overlap between county_fips_5 and US state code
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
    AND state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
    'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
    'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
    'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
    'VA','WA','WV','WI','WY','DC')
""")
fips_and_state = c.fetchone()[0]
print(f"  MX with county_fips_5 AND US state: {fips_and_state:,}")

# How many osm_import MX records have county_fips_5 but NULL state?
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND source='osm_import' 
    AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
    AND (state IS NULL OR state = '' OR state = 'None')
""")
osm_fips_no_state = c.fetchone()[0]
print(f"  osm_import MX with county_fips_5 but no state: {osm_fips_no_state:,}")

# Total fixable MX records:
# 1. US state code → US (501)
# 2. county_fips_5 + no state → US (adds the bulk)
# 3. US sources → US (just 1)

# But avoid double-counting
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (
        (state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
         'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
         'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
         'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
         'VA','WA','WV','WI','WY','DC'))
        OR 
        (county_fips_5 IS NOT NULL AND county_fips_5 != ''
         AND (state IS NULL OR state = '' OR state = 'None'))
    )
""")
total_fixable = c.fetchone()[0]
print(f"\nTOTAL MX records fixable (state code OR county_fips_5): {total_fixable:,}")

# Source breakdown of fixable
c.execute("""
    SELECT source, COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (
        (state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
         'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
         'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
         'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
         'VA','WA','WV','WI','WY','DC'))
        OR 
        (county_fips_5 IS NOT NULL AND county_fips_5 != ''
         AND (state IS NULL OR state = '' OR state = 'None'))
    )
    GROUP BY source ORDER BY COUNT(*) DESC
""")
print("\n=== Fixable MX records by source ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:40]:40s}  {r[1]:>8,}")

# Show faith breakdown
c.execute("""
    SELECT faith, COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (
        (state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
         'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
         'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
         'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
         'VA','WA','WV','WI','WY','DC'))
        OR 
        (county_fips_5 IS NOT NULL AND county_fips_5 != ''
         AND (state IS NULL OR state = '' OR state = 'None'))
    )
    GROUP BY faith ORDER BY COUNT(*) DESC
""")
print("\n=== Faith breakdown ===")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):20s}  {r[1]:>8,}")

db.close()

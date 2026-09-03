"""Better MX→US investigation — use state codes and source to find true mislabels"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# 1. MX records with a US state code = DEFINITELY mislabeled
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' AND state IN (
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
        'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
        'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
        'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
        'VA','WA','WV','WI','WY','DC','PR','GU','VI','AS'
    )
""")
state_mismatch = c.fetchone()[0]
print(f"1. MX records with a US state code: {state_mismatch:,}  ← DEFINITE")

# 2. MX records from US-specific sources
us_sources = [
    "irs", "irs+holy_sites_enrichment",
    "sbc_directory", "sbc_directory+holy_sites_enrichment",
    "sbc_scrape", "sbc_scrape+holy_sites_enrichment",
    "pcusa_api", "pcusa_api+holy_sites_enrichment",
    "umc_national", "umc_national+holy_sites_enrichment",
    "ag_directory", "ag_directory+holy_sites_enrichment",
    "cogic_scraper", "cogic_scraper+holy_sites_enrichment",
    "masstimes_nationwide", "masstimes_nationwide+holy_sites_enrichment",
    "catholic_diocese_scrape",
    "lcms_scraper", "lcms_scraper+holy_sites_enrichment",
    "coc_21stcc", "coc_21stcc+holy_sites_enrichment",
    "fwb_scraper", "fwb_scraper+holy_sites_enrichment",
    "csv_import", "csv_import+holy_sites_enrichment",
]

for src in us_sources:
    c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country='MX' AND source = ? AND (state IS NULL OR state = '' OR state = 'None')
    """, (src,))
    cnt = c.fetchone()[0]
    if cnt:
        print(f"2. MX records from {src:40s}: {cnt:>6,}")

# 3. MX records from overture with US city names
# Check overture_full MX records with latitude in US side
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'overture%'
    AND latitude >= 25
    AND longitude BETWEEN -125 AND -65
""")
overture_mx = c.fetchone()[0]
print(f"\n3. MX records from overture with lat>=25: {overture_mx:,}")

# 4. Sample overture MX records — are they US or MX?
c.execute("""
    SELECT rowid, name, source, city, state, latitude, longitude, faith
    FROM churches 
    WHERE country='MX' 
    AND source LIKE 'overture_full%'
    AND latitude >= 30
    AND longitude BETWEEN -125 AND -80
    LIMIT 30
""")
print("\n=== Overture MX records with lat>=30 ===")
for r in c.fetchall():
    print(f"  rowid={r[0]} name={str(r[1])[:55]:55s} src={r[2]:20s} city={str(r[3] or '')[:20]:20s} st={r[4]}  lat={r[5]:.4f} lon={r[6]:.4f}")

# 5. Also check: osm_import MX — these should be correct since OSM knows country
# But check osm_import north of ~32.5 (the safe US side)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'osm_import%'
    AND latitude >= 32.5
    AND longitude BETWEEN -125 AND -80
""")
osm_north = c.fetchone()[0]
print(f"\n5. osm_import MX records north of 32.5°N: {osm_north:,}")

# 6. holy_sites_import — check north of 32.5
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'holy_sites_import%'
    AND latitude >= 32.5
    AND longitude BETWEEN -125 AND -80
""")
holy_north = c.fetchone()[0]
print(f"6. holy_sites_import MX records north of 32.5°N: {holy_north:,}")

# 7. What about MX records at CA/OR/WA/OR latitudes?
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude >= 33
    AND longitude BETWEEN -125 AND -114
""")
ca_lat = c.fetchone()[0]
print(f"\n7. MX records at CA latitude (lat>=33, lon -125 to -114): {ca_lat:,}")

c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude >= 34
    AND longitude BETWEEN -125 AND -65
""")
very_north = c.fetchone()[0]
print(f"8. MX records north of 34°N (Texas panhandle+): {very_north:,}")

# 9. MX records north of 40°N
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND latitude >= 40
    AND longitude BETWEEN -125 AND -65
""")
super_north = c.fetchone()[0]
print(f"9. MX records north of 40°N (midwest+): {super_north:,}")

# 10. Sample some clearly-wrong ones
c.execute("""
    SELECT rowid, name, source, city, state, latitude, longitude 
    FROM churches 
    WHERE country='MX' AND latitude >= 40
    LIMIT 20
""")
print("\n=== Clearly wrong: MX records in midwest/north latitudes ===")
for r in c.fetchall():
    print(f"  rowid={r[0]} name={str(r[1])[:55]:55s} src={r[2]:20s} city={str(r[3] or '')[:20]:20s} st={r[4]}  lat={r[5]:.4f} lon={r[6]:.4f}")

# 11. city containing US state abbreviations in MX records
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (city LIKE '%, CA%' OR city LIKE '%, TX%' OR city LIKE '%, FL%' 
         OR city LIKE '%, NY%' OR city LIKE '%, AZ%')
""")
city_state = c.fetchone()[0]
print(f"\n11. MX records with US state in city field: {city_state:,}")

db.close()

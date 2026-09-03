"""Full scope of MX→US mislabeling fix"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# 1. DEFINITE: MX records with a US state code → fix country to US
c.execute("""
    SELECT state, COUNT(*) FROM churches 
    WHERE country='MX' AND state IN (
        'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
        'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
        'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
        'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
        'VA','WA','WV','WI','WY','DC','PR','GU','VI','AS'
    )
    GROUP BY state ORDER BY COUNT(*) DESC
""")
print("=== MX records with US state codes (definitely US) ===")
total_definite = 0
for r in c.fetchall():
    print(f"  state={r[0]:5s}  {r[1]:>6,}")
    total_definite += r[1]
print(f"  TOTAL: {total_definite:,}")

# 2. MX records from US-specific sources (without US state code)
c.execute("""
    SELECT source, COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (state IS NULL OR state = '' OR state = 'None')
    AND source IN (
        'irs', 'irs+holy_sites_enrichment',
        'sbc_directory', 'sbc_directory+holy_sites_enrichment',
        'sbc_scrape', 'sbc_scrape+holy_sites_enrichment',
        'pcusa_api', 'pcusa_api+holy_sites_enrichment',
        'masstimes_nationwide', 'masstimes_nationwide+holy_sites_enrichment',
        'catholic_diocese_scrape',
        'lcms_scraper', 'lcms_scraper+holy_sites_enrichment',
        'coc_21stcc', 'coc_21stcc+holy_sites_enrichment',
        'fwb_scraper', 'fwb_scraper+holy_sites_enrichment',
        'csv_import', 'csv_import+holy_sites_enrichment',
        'contacts', 'contacts+holy_sites_enrichment',
        'umc_national', 'umc_national+holy_sites_enrichment',
        'master'
    )
    GROUP BY source ORDER BY COUNT(*) DESC
""")
total_us_source = 0
print("\n=== MX records from US sources (definitely US) ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:45]:45s}  {r[1]:>6,}")
    total_us_source += r[1]
print(f"  TOTAL: {total_us_source:,}")

# 3. MX records with US-sounding city names (at lat >= 25)
# Look for "City, ST" pattern in city field
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND (state IS NULL OR state = '' OR state = 'None')
    AND source NOT IN ('irs', 'irs+holy_sites_enrichment', 'sbc_directory', 
                       'sbc_directory+holy_sites_enrichment', 'pcusa_api',
                       'pcusa_api+holy_sites_enrichment')
    AND city LIKE '%, __'  -- "CITYNAME, ST" pattern
    AND latitude >= 25
""")
city_state_pattern = c.fetchone()[0]
print(f"\n3. MX records with 'City, ST' in city field: {city_state_pattern:,}")

# 4. osm_import MX records — check if many have US city names
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'osm_import%'
    AND (state IS NULL OR state = '' OR state = 'None')
    AND city IS NOT NULL AND city != '' AND city != 'None'
    AND latitude >= 25
    AND (
        city LIKE '%, AL' OR city LIKE '%, AK' OR city LIKE '%, AZ' OR city LIKE '%, AR'
        OR city LIKE '%, CA' OR city LIKE '%, CO' OR city LIKE '%, CT' OR city LIKE '%, DE'
        OR city LIKE '%, FL' OR city LIKE '%, GA' OR city LIKE '%, HI' OR city LIKE '%, ID'
        OR city LIKE '%, IL' OR city LIKE '%, IN' OR city LIKE '%, IA' OR city LIKE '%, KS'
        OR city LIKE '%, KY' OR city LIKE '%, LA' OR city LIKE '%, ME' OR city LIKE '%, MD'
        OR city LIKE '%, MA' OR city LIKE '%, MI' OR city LIKE '%, MN' OR city LIKE '%, MS'
        OR city LIKE '%, MO' OR city LIKE '%, MT' OR city LIKE '%, NE' OR city LIKE '%, NV'
        OR city LIKE '%, NH' OR city LIKE '%, NJ' OR city LIKE '%, NM' OR city LIKE '%, NY'
        OR city LIKE '%, NC' OR city LIKE '%, ND' OR city LIKE '%, OH' OR city LIKE '%, OK'
        OR city LIKE '%, OR' OR city LIKE '%, PA' OR city LIKE '%, RI' OR city LIKE '%, SC'
        OR city LIKE '%, SD' OR city LIKE '%, TN' OR city LIKE '%, TX' OR city LIKE '%, UT'
        OR city LIKE '%, VT' OR city LIKE '%, VA' OR city LIKE '%, WA' OR city LIKE '%, WV'
        OR city LIKE '%, WI' OR city LIKE '%, WY' OR city LIKE '%, DC'
    )
""")
osm_city_state = c.fetchone()[0]
print(f"4. osm_import MX records with 'City, ST' in city: {osm_city_state:,}")

# 5. holy_sites_import — same
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'holy_sites_import%'
    AND (state IS NULL OR state = '' OR state = 'None')
    AND city IS NOT NULL AND city != '' AND city != 'None'
    AND latitude >= 25
    AND (
        city LIKE '%, AL' OR city LIKE '%, AK' OR city LIKE '%, AZ' OR city LIKE '%, AR'
        OR city LIKE '%, CA' OR city LIKE '%, CO' OR city LIKE '%, CT' OR city LIKE '%, DE'
        OR city LIKE '%, FL' OR city LIKE '%, GA' OR city LIKE '%, HI' OR city LIKE '%, ID'
        OR city LIKE '%, IL' OR city LIKE '%, IN' OR city LIKE '%, IA' OR city LIKE '%, KS'
        OR city LIKE '%, KY' OR city LIKE '%, LA' OR city LIKE '%, ME' OR city LIKE '%, MD'
        OR city LIKE '%, MA' OR city LIKE '%, MI' OR city LIKE '%, MN' OR city LIKE '%, MS'
        OR city LIKE '%, MO' OR city LIKE '%, MT' OR city LIKE '%, NE' OR city LIKE '%, NV'
        OR city LIKE '%, NH' OR city LIKE '%, NJ' OR city LIKE '%, NM' OR city LIKE '%, NY'
        OR city LIKE '%, NC' OR city LIKE '%, ND' OR city LIKE '%, OH' OR city LIKE '%, OK'
        OR city LIKE '%, OR' OR city LIKE '%, PA' OR city LIKE '%, RI' OR city LIKE '%, SC'
        OR city LIKE '%, SD' OR city LIKE '%, TN' OR city LIKE '%, TX' OR city LIKE '%, UT'
        OR city LIKE '%, VT' OR city LIKE '%, VA' OR city LIKE '%, WA' OR city LIKE '%, WV'
        OR city LIKE '%, WI' OR city LIKE '%, WY' OR city LIKE '%, DC'
    )
""")
holy_city_state = c.fetchone()[0]
print(f"5. holy_sites_import MX records with 'City, ST' in city: {holy_city_state:,}")

# 6. MX records from overture with US state in city field
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='MX' 
    AND source LIKE 'overture%'
    AND (state IS NULL OR state = '' OR state = 'None')
    AND city IS NOT NULL AND city != '' AND city != 'None'
    AND latitude >= 25
    AND (
        city LIKE '%, AL' OR city LIKE '%, AK' OR city LIKE '%, AZ' OR city LIKE '%, AR'
        OR city LIKE '%, CA' OR city LIKE '%, CO' OR city LIKE '%, CT' OR city LIKE '%, DE'
        OR city LIKE '%, FL' OR city LIKE '%, GA' OR city LIKE '%, HI' OR city LIKE '%, ID'
        OR city LIKE '%, IL' OR city LIKE '%, IN' OR city LIKE '%, IA' OR city LIKE '%, KS'
        OR city LIKE '%, KY' OR city LIKE '%, LA' OR city LIKE '%, ME' OR city LIKE '%, MD'
        OR city LIKE '%, MA' OR city LIKE '%, MI' OR city LIKE '%, MN' OR city LIKE '%, MS'
        OR city LIKE '%, MO' OR city LIKE '%, MT' OR city LIKE '%, NE' OR city LIKE '%, NV'
        OR city LIKE '%, NH' OR city LIKE '%, NJ' OR city LIKE '%, NM' OR city LIKE '%, NY'
        OR city LIKE '%, NC' OR city LIKE '%, ND' OR city LIKE '%, OH' OR city LIKE '%, OK'
        OR city LIKE '%, OR' OR city LIKE '%, PA' OR city LIKE '%, RI' OR city LIKE '%, SC'
        OR city LIKE '%, SD' OR city LIKE '%, TN' OR city LIKE '%, TX' OR city LIKE '%, UT'
        OR city LIKE '%, VT' OR city LIKE '%, VA' OR city LIKE '%, WA' OR city LIKE '%, WV'
        OR city LIKE '%, WI' OR city LIKE '%, WY' OR city LIKE '%, DC'
    )
""")
overture_city_state = c.fetchone()[0]
print(f"6. overture MX records with 'City, ST' in city: {overture_city_state:,}")

# 7. Total from overture+osm+holy with US state in city (excluding def account)
all_city_state = osm_city_state + holy_city_state + overture_city_state
# Remove overlap with US-state-code records (501)
all_city_state_minus_overlap = max(0, all_city_state - 501)
print(f"\n7. Non-overlap city-state pattern total: {all_city_state_minus_overlap:,}")

# 8. Grand total approach: check address field for US indicators  
c.execute("""
    SELECT SUM(city_state_indicators + source_indicators + state_indicators) as grand_total
    FROM (
        SELECT 
            CASE WHEN (state IS NOT NULL AND state != '' AND state != 'None'
                  AND state IN ('AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA',
                  'HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI',
                  'MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND',
                  'OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
                  'VA','WA','WV','WI','WY','DC')) 
            THEN 1 ELSE 0 END as state_indicators,
            CASE WHEN source IN ('irs','irs+holy_sites_enrichment','sbc_directory',
                  'sbc_directory+holy_sites_enrichment','pcusa_api',
                  'pcusa_api+holy_sites_enrichment','masstimes_nationwide',
                  'masstimes_nationwide+holy_sites_enrichment','catholic_diocese_scrape',
                  'lcms_scraper','lcms_scraper+holy_sites_enrichment','coc_21stcc',
                  'coc_21stcc+holy_sites_enrichment','fwb_scraper',
                  'fwb_scraper+holy_sites_enrichment','csv_import',
                  'csv_import+holy_sites_enrichment','contacts',
                  'contacts+holy_sites_enrichment','umc_national',
                  'umc_national+holy_sites_enrichment','master')
            AND (state IS NULL OR state = '' OR state = 'None')
            THEN 1 ELSE 0 END as source_indicators,
            0 as city_state_indicators
        FROM churches
        WHERE country='MX'
    )
""")
r = c.fetchone()
grand = r[0] if r else 0
print(f"\n8. COMBINED: MX records that are definitely US: {grand:,}")

db.close()

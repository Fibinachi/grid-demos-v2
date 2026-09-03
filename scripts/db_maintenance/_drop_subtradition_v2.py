"""Drop subtradition column and recreate affected view."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

# 1. Drop the view that references subtradition
print('Dropping v_churches view...')
db.execute('DROP VIEW IF EXISTS v_churches')

# 2. Drop the column
print('Dropping subtradition column...')
db.execute('ALTER TABLE churches DROP COLUMN subtradition')
db.commit()

# 3. Recreate the view without subtradition
print('Recreating v_churches view...')
db.execute("""
    CREATE VIEW v_churches AS
    SELECT c.id, c.name, c.family, c.tradition_legacy, c.religion_type, 
           c.normalized_name, c.address, c.city, c.state, c.zip, c.zip5, c.zip4, 
           c.ein, c.ntee_code, c.latitude, c.longitude, c.geocode_source, c.fips, 
           c.country, c.source, c.denomination_affiliation, c.address_source, 
           c.holy_site_id, c.landmark_type, c.is_landmark, c.heritage_status, 
           c.height_m, c.width_m, c.length_m, c.area_m2, c.capacity, c.building_year, 
           c.source_primary, c.source_secondary, c.osm_id, c.osm_type, c.osm_version, 
           c.osm_timestamp, c.wikidata_qid, c.wikidata_last_modified, c.overture_id, 
           c.confidence_score, c.cra_bn, c.cra_category, c.cra_sub_category, 
           c.cra_designation, c.mosque_type, c.canonical_status, c.heritage_source, 
           c.dedication, c.muslim_affiliation, c.muslim_confidence, 
           c.muslim_classification_source, c.muslim_updated, c.name_original, 
           c.age_centuries, c.county, c.county_fips_5, c.name_transliterated, 
           c.continent, c.region_un, c.subregion, 
           COALESCE(f.name, 'Other') AS faith, 
           COALESCE(trad.name, 'Unclassified') AS faith_tradition, 
           COALESCE(fam.name, 'Unclassified') AS family, 
           COALESCE(denom.name, 'Unclassified') AS denomination
    FROM churches c
    LEFT JOIN taxonomy denom ON c.taxonomy_id = denom.id
    LEFT JOIN taxonomy fam ON denom.family_id = fam.id
    LEFT JOIN taxonomy trad ON denom.tradition_id = trad.id
    LEFT JOIN taxonomy f ON denom.root_id = f.id
""")
db.commit()

# Verify
cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()]
print(f'Columns remaining: {len(cols)}')
print(f'subtradition present: {"subtradition" in cols}')

# Verify view works
try:
    r = db.execute('SELECT COUNT(*) FROM v_churches').fetchone()
    print(f'v_churches works: {r[0]:,} rows')
except Exception as e:
    print(f'v_churches error: {e}')

db.close()
print('Done!')

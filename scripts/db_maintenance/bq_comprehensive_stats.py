"""BQ churches table stats for comparison with local SQLite."""
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')

q = '''
SELECT 
  COUNT(*) as total,
  COUNTIF(denomination IS NOT NULL AND denomination != '') as denominated,
  COUNTIF(latitude IS NOT NULL) as geocoded,
  COUNTIF(country IS NOT NULL AND country != '') as country_filled,
  COUNTIF(faith IS NOT NULL AND faith != '') as faith_filled,
  COUNTIF(faith_tradition IS NOT NULL AND faith_tradition != '') as faith_tradition,
  COUNTIF(fips IS NOT NULL AND fips != '') as fips,
  COUNTIF(osm_id IS NOT NULL) as osm,
  COUNTIF(overture_id IS NOT NULL) as overture,
  COUNTIF(wikidata_qid IS NOT NULL) as wikidata,
  COUNTIF(normalized_name IS NOT NULL AND normalized_name != '') as norm_name,
  COUNTIF(city IS NOT NULL AND city != '') as city,
  COUNTIF(state IS NOT NULL AND state != '') as state,
  COUNTIF(zip IS NOT NULL AND zip != '') as zip,
  COUNTIF(ein IS NOT NULL AND ein != '') as ein,
  COUNTIF(mosque_type IS NOT NULL AND mosque_type != '') as mosque_type,
  COUNTIF(canonical_status IS NOT NULL AND canonical_status != '') as canonical,
  COUNTIF(confidence_score IS NOT NULL) as confidence,
  COUNTIF(address IS NOT NULL AND address != '') as address,
  COUNTIF(geocode_source IS NOT NULL AND geocode_source != '') as geocode_src,
  COUNTIF(id IS NOT NULL) as with_id,
  COUNTIF(landmark_type IS NOT NULL AND landmark_type != '') as landmark,
  COUNTIF(building_year IS NOT NULL) as building_yr,
  COUNTIF(heritage_status IS NOT NULL AND heritage_status != '') as heritage,
  COUNTIF(cra_bn IS NOT NULL) as cra_canada,
FROM American_Religious_Infrastructure.churches
'''
rows = client.query(q).result()
r = list(rows)[0]
total = r['total']
print(f'=== BQ churches table ({total:,} total) ===')
print()

fields = [
    ('With id', 'with_id'),
    ('Geocoded (lat/lon)', 'geocoded'),
    ('Geocode source filled', 'geocode_src'),
    ('Address filled', 'address'),
    ('City filled', 'city'),
    ('State filled', 'state'),
    ('ZIP filled', 'zip'),
    ('Country filled', 'country_filled'),
    ('FIPS filled', 'fips'),
    ('Normalized name', 'norm_name'),
    ('Faith filled', 'faith_filled'),
    ('Faith tradition', 'faith_tradition'),
    ('Denominated', 'denominated'),
    ('EIN filled', 'ein'),
    ('OSM sourced', 'osm'),
    ('Overture sourced', 'overture'),
    ('Wikidata sourced', 'wikidata'),
    ('CRA Canada', 'cra_canada'),
    ('Mosque type', 'mosque_type'),
    ('Canonical status', 'canonical'),
    ('Confidence scored', 'confidence'),
    ('Landmark type', 'landmark'),
    ('Building year', 'building_yr'),
    ('Heritage status', 'heritage'),
]

for label, f in fields:
    val = r[f]
    if val is None:
        val = 0
    pct = (val / total * 100) if total > 0 else 0
    print(f'  {label:<25s} {int(val):>12,}  ({pct:.1f}%)')

# Faith distribution
print()
print('=== FAITH DISTRIBUTION (BQ) ===')
q2 = '''
SELECT faith, COUNT(*) as cnt
FROM American_Religious_Infrastructure.churches
GROUP BY faith ORDER BY cnt DESC LIMIT 12
'''
for row in client.query(q2).result():
    pct = row['cnt'] / total * 100
    label = row['faith'] if row['faith'] else '(null)'
    print(f'  {label:<30s} {row["cnt"]:>10,}  ({pct:.1f}%)')

# Top countries
print()
print('=== TOP COUNTRIES (BQ) ===')
q3 = '''
SELECT country, COUNT(*) as cnt
FROM American_Religious_Infrastructure.churches
WHERE country IS NOT NULL AND country != ''
GROUP BY country ORDER BY cnt DESC LIMIT 15
'''
for row in client.query(q3).result():
    pct = row['cnt'] / total * 100
    print(f'  {row["country"]:<30s} {row["cnt"]:>10,}  ({pct:.1f}%)')

# Overture holy staging
print()
q4 = '''
SELECT COUNT(*) as total,
       COUNTIF(website IS NOT NULL AND website != '') as with_web
FROM American_Religious_Infrastructure.overture_holy_staging
'''
rows4 = client.query(q4).result()
r4 = list(rows4)[0]
print(f'overture_holy_staging: {r4["total"]:,} rows, {r4["with_web"]:,} with websites')

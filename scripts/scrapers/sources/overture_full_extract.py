"""
Extract ALL church_cathedral from Overture Maps, deduplicate against our churches,
and write new ones to a BQ staging table + local CSV for SQLite import.

Strategy:
1. Extract all US church_cathedral from Overture (name, address, city, state, lat, lon)
2. LEFT JOIN against our churches table on normalized (name, state)
3. Only keep non-matching ones
4. Write to BQ staging table + local CSV
"""
import os, json, tempfile, csv
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

print('=== Step 1: Extract ALL church_cathedral from Overture ===')
print('(this queries the full US bbox — may take 2-3 minutes)')

# Extract all US church_cathedral with names
sql_extract = '''
SELECT 
    id AS overture_id,
    names.primary AS name,
    addresses.list[SAFE_OFFSET(0)].element.freeform AS address,
    addresses.list[SAFE_OFFSET(0)].element.locality AS city,
    addresses.list[SAFE_OFFSET(0)].element.region AS state,
    addresses.list[SAFE_OFFSET(0)].element.postcode AS zip,
    COALESCE(brand.names.primary, '') AS brand_name,
    confidence,
    ST_Y(geometry) AS latitude,
    ST_X(geometry) AS longitude
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
  AND names.primary IS NOT NULL
  AND names.primary != ''
'''

extracted = list(client.query(sql_extract).result())
print(f'  Extracted: {len(extracted):,} churches')

# ── Step 2: Dedup in BQ ──
print('\n=== Step 2: Write to staging table + dedup ===')

# First write to staging
staging_ref = f'{PROJECT}.{DATASET}.overture_churches_staging'
client.delete_table(staging_ref, not_found_ok=True)

tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
for r in extracted:
    tmp.write(json.dumps({
        'overture_id': r.overture_id,
        'name': r.name,
        'address': r.address,
        'city': r.city,
        'state': r.state,
        'zip': r.zip,
        'brand_name': r.brand_name,
        'confidence': r.confidence,
        'latitude': r.latitude,
        'longitude': r.longitude,
    }) + '\n')
tmp.close()

schema = [
    SchemaField('overture_id', 'STRING'),
    SchemaField('name', 'STRING'), SchemaField('address', 'STRING'),
    SchemaField('city', 'STRING'), SchemaField('state', 'STRING'),
    SchemaField('zip', 'STRING'), SchemaField('brand_name', 'STRING'),
    SchemaField('confidence', 'FLOAT64'),
    SchemaField('latitude', 'FLOAT64'), SchemaField('longitude', 'FLOAT64'),
]
config = LoadJobConfig(schema=schema, source_format='NEWLINE_DELIMITED_JSON', write_disposition='WRITE_TRUNCATE')
with open(tmp.name, 'rb') as f:
    job = client.load_table_from_file(f, staging_ref, job_config=config)
job.result()
os.unlink(tmp.name)
print(f'  Wrote {len(extracted):,} to {staging_ref}')

# Now dedup against our churches table
print('\n=== Step 3: Deduplicate against existing churches ===')
sql_dedup = f'''
WITH existing AS (
  SELECT DISTINCT LOWER(TRIM(COALESCE(name,''))) AS name_key, 
         LOWER(TRIM(COALESCE(state,''))) AS state_key
  FROM `{PROJECT}.{DATASET}.churches`
  WHERE name IS NOT NULL AND state IS NOT NULL
),
new_churches AS (
  SELECT o.*
  FROM `{PROJECT}.{DATASET}.overture_churches_staging` o
  LEFT JOIN existing e 
    ON LOWER(TRIM(COALESCE(o.name,''))) = e.name_key
   AND LOWER(TRIM(COALESCE(o.state,''))) = e.state_key
  WHERE e.name_key IS NULL
)
SELECT COUNT(*) as cnt FROM new_churches
'''
dedup_result = list(client.query(sql_dedup).result())
new_count = dedup_result[0].cnt
print(f'  New churches (not in DB): {new_count:,}')
print(f'  Duplicates (already in DB): {len(extracted) - new_count:,}')

# ── Step 4: Write new churches to final table ──
print('\n=== Step 4: Write new churches to overture_churches_new ===')
new_ref = f'{PROJECT}.{DATASET}.overture_churches_new'

sql_create_new = f'''
CREATE OR REPLACE TABLE `{new_ref}` AS
WITH existing AS (
  SELECT DISTINCT LOWER(TRIM(COALESCE(name,''))) AS name_key, 
         LOWER(TRIM(COALESCE(state,''))) AS state_key
  FROM `{PROJECT}.{DATASET}.churches`
  WHERE name IS NOT NULL AND state IS NOT NULL
)
SELECT o.*
FROM `{PROJECT}.{DATASET}.overture_churches_staging` o
LEFT JOIN existing e 
  ON LOWER(TRIM(COALESCE(o.name,''))) = e.name_key
 AND LOWER(TRIM(COALESCE(o.state,''))) = e.state_key
WHERE e.name_key IS NULL
'''
client.query(sql_create_new).result()
print(f'  Created: {new_ref}')
print(f'  New churches: {new_count:,}')

# ── Step 5: Download as CSV for SQLite import ──
print('\n=== Step 5: Download to CSV ===')
sql_download = f'SELECT * FROM `{new_ref}`'
rows = list(client.query(sql_download).result())
csv_path = 'E:/grid/data/overture_churches_new.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['overture_id','name','address','city','state','zip','brand_name','confidence','latitude','longitude'])
    for r in rows:
        w.writerow([r.overture_id, r.name, r.address, r.city, r.state, r.zip, r.brand_name, r.confidence, r.latitude, r.longitude])
print(f'  Saved {len(rows):,} rows to {csv_path}')

# ── Step 6: Summary ──
print(f'\n=== SUMMARY ===')
print(f'  Total Overture church_cathedral (US): {len(extracted):,}')
print(f'  Already in our DB: {len(extracted) - new_count:,}')
print(f'  NEW churches to import: {new_count:,}')
print(f'  CSV ready: {csv_path}')
print(f'  BQ table: {new_ref}')

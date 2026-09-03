"""
Extract ALL church_cathedral from Overture Maps using BQ batch query,
then deduplicate and download to CSV.
"""
import os, csv
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

# ── Step 1: CREATE TABLE AS SELECT (batch, not interactive) ──
print('=== Step 1: Creating overture_churches_staging via batch query ===')
staging_ref = f'{PROJECT}.{DATASET}.overture_churches_staging'

sql_create = f'''
CREATE OR REPLACE TABLE `{staging_ref}` AS
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

job_config = bigquery.QueryJobConfig(priority=bigquery.QueryPriority.BATCH)
job = client.query(sql_create, job_config=job_config)
print('  Running batch CREATE TABLE job...', flush=True)
result = job.result()
total_rows = list(client.query(f'SELECT COUNT(*) as cnt FROM `{staging_ref}`').result())[0].cnt
print(f'  Done. {total_rows:,} churches in staging')

# ── Step 2: Create deduplicated table ──
print('\n=== Step 2: Deduplicating against existing churches ===')
new_ref = f'{PROJECT}.{DATASET}.overture_churches_new'

sql_dedup = f'''
CREATE OR REPLACE TABLE `{new_ref}` AS
SELECT o.*
FROM `{staging_ref}` o
WHERE NOT EXISTS (
    SELECT 1 FROM `{PROJECT}.{DATASET}.churches` c
    WHERE LOWER(TRIM(COALESCE(c.name,''))) = LOWER(TRIM(COALESCE(o.name,'')))
      AND LOWER(TRIM(COALESCE(c.state,''))) = LOWER(TRIM(COALESCE(o.state,'')))
)
'''

job2 = client.query(sql_dedup, job_config=job_config)
print('  Running batch dedup job...', flush=True)
job2.result()
new_count = list(client.query(f'SELECT COUNT(*) as cnt FROM `{new_ref}`').result())[0].cnt
dup_count = total_rows - new_count
print(f'  Done. New: {new_count:,} | Duplicates: {dup_count:,} | New rate: {100*new_count/total_rows:.1f}%')

# ── Step 3: Download to CSV ──
print(f'\n=== Step 3: Downloading {new_count:,} new churches to CSV ===')
csv_path = 'E:/grid/data/overture_churches_new.csv'

sql_download = f'SELECT * FROM `{new_ref}` ORDER BY state, city, name'
rows = list(client.query(sql_download).result())

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['overture_id','name','address','city','state','zip','brand_name','confidence','latitude','longitude'])
    for r in rows:
        w.writerow([r.overture_id, r.name, r.address, r.city, r.state, r.zip, r.brand_name, r.confidence, r.latitude, r.longitude])

print(f'  Saved {len(rows):,} rows to {csv_path}')

# ── Step 4: Summary ──
print(f'\n=== SUMMARY ===')
print(f'  Total Overture church_cathedral (US): {total_rows:,}')
print(f'  Already in our DB: {dup_count:,}')
print(f'  NEW churches to import: {new_count:,}')
print(f'  CSV: {csv_path}')
print(f'  BQ staging: {staging_ref}')
print(f'  BQ new-only: {new_ref}')

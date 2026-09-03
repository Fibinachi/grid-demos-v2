"""
Backfill county_fips for ALL churches with coordinates but no FIPS.
Uses BQ spatial join against geo_us_boundaries.counties.
"""
import os, sqlite3, json, tempfile
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

# Step 1: Upload churches needing FIPS to BQ
print('=== Step 1: Gather churches without county_fips ===')
conn = sqlite3.connect('churches.db')
rows = conn.execute("""
    SELECT id, latitude, longitude 
    FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    AND (county_fips IS NULL OR county_fips = '')
""").fetchall()
conn.close()
print(f'  {len(rows):,} churches need county_fips')

# Write to temp JSON for BQ upload
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
for r in rows:
    tmp.write(json.dumps({'id': r[0], 'latitude': r[1], 'longitude': r[2]}) + '\n')
tmp.close()

staging_ref = f'{PROJECT}.{DATASET}._fips_backfill_staging'
client.delete_table(staging_ref, not_found_ok=True)
schema = [SchemaField('id','FLOAT64'), SchemaField('latitude','FLOAT64'), SchemaField('longitude','FLOAT64')]
config = LoadJobConfig(schema=schema, source_format='NEWLINE_DELIMITED_JSON', write_disposition='WRITE_TRUNCATE')
with open(tmp.name, 'rb') as f:
    job = client.load_table_from_file(f, staging_ref, job_config=config)
job.result()
os.unlink(tmp.name)
print(f'  Uploaded to {staging_ref}')

# Step 2: Spatial join with counties
print('\n=== Step 2: Spatial join with county boundaries ===')
result_ref = f'{PROJECT}.{DATASET}._fips_backfill_result'
sql = f'''
CREATE OR REPLACE TABLE `{result_ref}` AS
SELECT 
    s.id,
    c.county_fips_code AS county_fips,
    c.county_name
FROM `{staging_ref}` s
JOIN `bigquery-public-data.geo_us_boundaries.counties` c
  ON ST_WITHIN(ST_GEOGPOINT(s.longitude, s.latitude), c.county_geom)
'''

job_config = bigquery.QueryJobConfig(priority=bigquery.QueryPriority.BATCH)
job = client.query(sql, job_config=job_config)
print('  Running batch spatial join...', flush=True)
job.result()
matched = list(client.query(f'SELECT COUNT(*) as cnt FROM `{result_ref}`').result())[0].cnt
print(f'  Matched: {matched:,} / {len(rows):,} ({100*matched/len(rows):.1f}%)')

# Step 3: Download results and update SQLite
print('\n=== Step 3: Downloading results ===')
results = list(client.query(f'SELECT * FROM `{result_ref}`').result())
print(f'  Downloaded {len(results):,} rows')

print('\n=== Step 4: Updating SQLite ===')
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')

updated = 0
batch = []
for r in results:
    batch.append((r.county_fips, r.county_name, int(r.id)))
    if len(batch) >= 10000:
        conn.executemany("UPDATE churches SET county_fips=?, county_name=? WHERE id=?", batch)
        updated += len(batch)
        print(f'  {updated:,}...', flush=True)
        batch = []
        conn.commit()
if batch:
    conn.executemany("UPDATE churches SET county_fips=?, county_name=? WHERE id=?", batch)
    updated += len(batch)
    conn.commit()

print(f'  Total updated: {updated:,}')

# Verify
remaining = conn.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND (county_fips IS NULL OR county_fips = '')").fetchone()[0]
print(f'  Remaining without FIPS: {remaining:,}')

# Re-check Juab
juab = conn.execute("SELECT COUNT(*) FROM churches WHERE county_fips='49023'").fetchone()[0]
print(f'\n  Juab County churches: {juab}')
for r in conn.execute("SELECT name, city FROM churches WHERE county_fips='49023' LIMIT 10").fetchall():
    print(f'    {r[0][:45]:45s} {r[1]}')

# Clean up
client.delete_table(staging_ref, not_found_ok=True)
client.delete_table(result_ref, not_found_ok=True)

conn.close()
print('\nDone.')

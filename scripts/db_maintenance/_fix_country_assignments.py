"""
Fix country assignments for CA+MX churches using spatial verification.
Churches physically in US territory get country='US', etc.
"""
import os, sqlite3, json, tempfile
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField, QueryJobConfig

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

# ── Show current state ──
conn = sqlite3.connect('churches.db')
print('=== CURRENT COUNTRY COUNTS ===')
for r in conn.execute("SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC"):
    print(f'  {r[0] or "NULL":5s} {r[1]:>10,}')

# ── Upload all non-US churches with coords ──
non_us = conn.execute("""
    SELECT id, latitude, longitude, country FROM churches 
    WHERE country != 'US' AND latitude IS NOT NULL
""").fetchall()
conn.close()
print(f'\nNon-US churches with coords: {len(non_us):,}')

tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
for r in non_us:
    tmp.write(json.dumps({'id': r[0], 'lat': r[1], 'lon': r[2], 'old_country': r[3]}) + '\n')
tmp.close()

staging = f'{PROJECT}.{DATASET}._country_fix_staging'
client.delete_table(staging, not_found_ok=True)
config = LoadJobConfig(
    schema=[SchemaField('id','FLOAT64'), SchemaField('lat','FLOAT64'), 
            SchemaField('lon','FLOAT64'), SchemaField('old_country','STRING')],
    source_format='NEWLINE_DELIMITED_JSON', write_disposition='WRITE_TRUNCATE')
with open(tmp.name, 'rb') as f:
    client.load_table_from_file(f, staging, job_config=config).result()
os.unlink(tmp.name)
print(f'Uploaded to {staging}')

# ── Spatial join against country boundaries ──
print('\n=== Spatial join: which country are they actually in? ===')
result_ref = f'{PROJECT}.{DATASET}._country_fix_result'
sql = f'''
CREATE OR REPLACE TABLE `{result_ref}` AS
SELECT 
    CAST(s.id AS INT64) as church_id,
    s.old_country,
    d.names.primary AS actual_country_name,
    d.country AS actual_country_code
FROM `{staging}` s
JOIN `bigquery-public-data.overture_maps.division` d
  ON ST_WITHIN(ST_GEOGPOINT(s.lon, s.lat), d.geometry)
WHERE d.subtype = 'country'
'''
job = client.query(sql, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
print('Running...', flush=True)
job.result()
matched = list(client.query(f'SELECT COUNT(*) as cnt FROM `{result_ref}`').result())[0].cnt
print(f'Matched: {matched:,} / {len(non_us):,}')

# ── Download and analyze ──
print('\n=== Mismatches ===')
results = list(client.query(f'SELECT * FROM `{result_ref}`').result())

mismatches = []
for r in results:
    actual = (r.actual_country_code or '').upper()
    old = (r.old_country or '').upper()
    # Map country names to codes
    name_map = {'UNITED STATES': 'US', 'MEXICO': 'MX', 'CANADA': 'CA',
                'UNITED STATES OF AMERICA': 'US', 'ESTADOS UNIDOS MEXICANOS': 'MX'}
    actual = name_map.get(r.actual_country_name.upper() if r.actual_country_name else '', actual)
    if actual and actual != old:
        mismatches.append((actual, old, int(r.church_id)))

print(f'Churches with wrong country: {len(mismatches):,}')
if mismatches:
    from collections import Counter
    changes = Counter(f'{old}->{new}' for new, old, _ in mismatches)
    for change, count in changes.most_common():
        print(f'  {change}: {count:,}')

# ── Update SQLite ──
print('\n=== Updating SQLite ===')
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')

batch = [(new_country, cid) for new_country, old_country, cid in mismatches]
if batch:
    conn.executemany("UPDATE churches SET country=? WHERE id=?", batch)
    conn.commit()
print(f'Updated {len(batch):,} churches')

# ── Final counts ──
print('\n=== CORRECTED COUNTRY COUNTS ===')
for r in conn.execute("SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC"):
    print(f'  {r[0] or "NULL":5s} {r[1]:>10,}')
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'  TOTAL: {total:,}')

# Samples
print('\n=== SAMPLES OF FIXES ===')
for r in conn.execute("""
    SELECT name, city, state, country FROM churches 
    WHERE country='US' AND state IN ('BC','ON','QC','CMX','SLP','BCS','CHH')
    LIMIT 8
""").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]:5s} -> {r[3]}')

conn.close()
client.delete_table(staging, not_found_ok=True)
client.delete_table(result_ref, not_found_ok=True)
print('Done.')

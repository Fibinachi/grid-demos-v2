"""Use Overture division table to assign Mexican admin codes to churches"""
import os, sqlite3, json, tempfile
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField, QueryJobConfig

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

# ── Step 1: Explore Mexico division levels ──
print('=== Mexico admin levels in Overture ===')
sql_levels = '''
SELECT admin_level, subtype, COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.division`
WHERE country = 'MX'
GROUP BY 1, 2
ORDER BY 1, 2
'''
for r in client.query(sql_levels).result():
    print(f'  level={r.admin_level}  subtype={r.subtype or "?"}  count={r.cnt:,}')

# ── Step 2: Upload MX churches without admin codes to BQ ──
print('\n=== Uploading MX churches to BQ ===')
conn = sqlite3.connect('churches.db')
mx_rows = conn.execute("""
    SELECT id, latitude, longitude FROM churches 
    WHERE country='MX' AND latitude IS NOT NULL 
    AND (county_fips IS NULL OR county_fips = '')
""").fetchall()
conn.close()
print(f'  MX churches needing admin codes: {len(mx_rows):,}')

if mx_rows:
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    for r in mx_rows:
        tmp.write(json.dumps({'id': r[0], 'latitude': r[1], 'longitude': r[2]}) + '\n')
    tmp.close()
    
    staging = f'{PROJECT}.{DATASET}._mx_admin_staging'
    client.delete_table(staging, not_found_ok=True)
    config = LoadJobConfig(
        schema=[SchemaField('id','FLOAT64'), SchemaField('latitude','FLOAT64'), SchemaField('longitude','FLOAT64')],
        source_format='NEWLINE_DELIMITED_JSON', write_disposition='WRITE_TRUNCATE')
    with open(tmp.name, 'rb') as f:
        client.load_table_from_file(f, staging, job_config=config).result()
    os.unlink(tmp.name)
    print(f'  Uploaded to {staging}')

    # ── Step 3: Spatial join with Overture divisions ──
    print('\n=== Spatial join with Mexico divisions ===')
    result_ref = f'{PROJECT}.{DATASET}._mx_admin_result'
    
    # Match to locality (53K), county (2,475), neighborhood (10K) divisions
    sql_join = f'''
    CREATE OR REPLACE TABLE `{result_ref}` AS
    WITH loc_match AS (
        SELECT CAST(s.id AS INT64) as church_id, d.id AS division_id, d.subtype,
               d.names.primary AS division_name,
               ROW_NUMBER() OVER (PARTITION BY CAST(s.id AS INT64) ORDER BY ST_AREA(d.geometry) ASC) as rn
        FROM `{staging}` s
        JOIN `bigquery-public-data.overture_maps.division_area` d
          ON ST_WITHIN(ST_GEOGPOINT(s.longitude, s.latitude), d.geometry)
        WHERE d.country = 'MX' AND d.subtype IN ('locality', 'county', 'neighborhood')
    )
    SELECT church_id as id, division_id, subtype, division_name
    FROM loc_match WHERE rn = 1
    '''
    
    job = client.query(sql_join, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
    print('  Running spatial join...', flush=True)
    job.result()
    
    matched = list(client.query(f'SELECT COUNT(*) as cnt FROM `{result_ref}`').result())[0].cnt
    print(f'  Matched to locality/county/neighborhood: {matched:,} / {len(mx_rows):,} ({100*matched/len(mx_rows):.1f}%)')
    
    # ── Step 4: Download and update SQLite ──
    print('\n=== Downloading results and updating SQLite ===')
    results = list(client.query(f'SELECT * FROM `{result_ref}`').result())
    print(f'  Downloaded {len(results):,} rows')
    
    conn = sqlite3.connect('churches.db')
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('PRAGMA synchronous=OFF')
    
    # Add mx_admin_level column if needed
    if 'mx_admin_level' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN mx_admin_level INTEGER')
    if 'mx_division_id' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN mx_division_id TEXT')
    if 'mx_division_name' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN mx_division_name TEXT')
    if 'mx_admin_subtype' not in [r[1] for r in conn.execute('PRAGMA table_info(churches)')]:
        conn.execute('ALTER TABLE churches ADD COLUMN mx_admin_subtype TEXT')
    
    updated = 0
    batch = []
    for r in results:
        batch.append((r.subtype, r.division_id, r.division_name, int(r.id)))
        if len(batch) >= 5000:
            conn.executemany("""
                UPDATE churches SET mx_admin_subtype=?, mx_division_id=?, 
                mx_division_name=? WHERE id=?
            """, batch)
            updated += len(batch)
            print(f'  {updated:,}...', flush=True)
            batch = []
            conn.commit()
    if batch:
        conn.executemany("""
            UPDATE churches SET mx_admin_subtype=?, mx_division_id=?, 
            mx_division_name=? WHERE id=?
        """, batch)
        updated += len(batch)
        conn.commit()
    
    print(f'  Total updated: {updated:,}')
    
    # Sample
    print('\n=== SAMPLES ===')
    for r in conn.execute("""
        SELECT name, city, state, mx_division_name, mx_admin_subtype
        FROM churches WHERE country='MX' AND mx_division_name IS NOT NULL
        LIMIT 10
    """).fetchall():
        print(f'  {r[0][:40]:40s} {r[1]:15s} {r[2]}  div={r[3]}  type={r[4]}')
    
    # Cleanup
    client.delete_table(staging, not_found_ok=True)
    client.delete_table(result_ref, not_found_ok=True)
    conn.close()

print('Done.')

"""
Extract Canada + Mexico church_cathedral from Overture Maps,
deduplicate, download CSV, import to SQLite with country codes.
"""
import os, csv, json, tempfile, sqlite3
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField, QueryJobConfig

client = bigquery.Client(project='american-rel-infra')
PROJECT = 'american-rel-infra'
DATASET = 'American_Religious_Infrastructure'

# ── Step 1: Extract Canada to BQ staging ──
print('=== CANADA: Extract + dedup ===')
ca_staging = f'{PROJECT}.{DATASET}.overture_canada_staging'
sql_ca = f'''
CREATE OR REPLACE TABLE `{ca_staging}` AS
SELECT 
    id AS overture_id,
    names.primary AS name,
    addresses.list[SAFE_OFFSET(0)].element.freeform AS address,
    addresses.list[SAFE_OFFSET(0)].element.locality AS city,
    addresses.list[SAFE_OFFSET(0)].element.region AS state,
    addresses.list[SAFE_OFFSET(0)].element.postcode AS zip,
    confidence,
    ST_Y(geometry) AS latitude,
    ST_X(geometry) AS longitude
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -141.0 AND -52.0
  AND bbox.ymin BETWEEN 41.0 AND 83.0
  AND names.primary IS NOT NULL AND names.primary != ''
  AND addresses.list[SAFE_OFFSET(0)].element.region IS NOT NULL
'''
job = client.query(sql_ca, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
print('  Extracting Canada...', flush=True)
job.result()
ca_total = list(client.query(f'SELECT COUNT(*) as cnt FROM `{ca_staging}`').result())[0].cnt
print(f'  Canada total: {ca_total:,}')

# Dedup Canada against existing churches
ca_new_ref = f'{PROJECT}.{DATASET}.overture_canada_new'
sql_ca_dedup = f'''
CREATE OR REPLACE TABLE `{ca_new_ref}` AS
SELECT o.*
FROM `{ca_staging}` o
WHERE NOT EXISTS (
    SELECT 1 FROM `{PROJECT}.{DATASET}.churches` c
    WHERE LOWER(TRIM(COALESCE(c.name,''))) = LOWER(TRIM(COALESCE(o.name,'')))
      AND LOWER(TRIM(COALESCE(c.state,''))) = LOWER(TRIM(COALESCE(o.state,'')))
      AND c.country = 'CA'
)
'''
job = client.query(sql_ca_dedup, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
print('  Deduplicating Canada...', flush=True)
job.result()
ca_new = list(client.query(f'SELECT COUNT(*) as cnt FROM `{ca_new_ref}`').result())[0].cnt
print(f'  Canada new: {ca_new:,} ({100*ca_new/ca_total:.1f}% of {ca_total:,})')

# ── Step 2: Extract Mexico ──
print('\n=== MEXICO: Extract + dedup ===')
mx_staging = f'{PROJECT}.{DATASET}.overture_mexico_staging'
sql_mx = f'''
CREATE OR REPLACE TABLE `{mx_staging}` AS
SELECT 
    id AS overture_id,
    names.primary AS name,
    addresses.list[SAFE_OFFSET(0)].element.freeform AS address,
    addresses.list[SAFE_OFFSET(0)].element.locality AS city,
    addresses.list[SAFE_OFFSET(0)].element.region AS state,
    addresses.list[SAFE_OFFSET(0)].element.postcode AS zip,
    confidence,
    ST_Y(geometry) AS latitude,
    ST_X(geometry) AS longitude
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -118.0 AND -86.0
  AND bbox.ymin BETWEEN 14.0 AND 33.0
  AND names.primary IS NOT NULL AND names.primary != ''
  AND addresses.list[SAFE_OFFSET(0)].element.region IS NOT NULL
'''
job = client.query(sql_mx, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
print('  Extracting Mexico...', flush=True)
job.result()
mx_total = list(client.query(f'SELECT COUNT(*) as cnt FROM `{mx_staging}`').result())[0].cnt
print(f'  Mexico total: {mx_total:,}')

# Dedup Mexico
mx_new_ref = f'{PROJECT}.{DATASET}.overture_mexico_new'
sql_mx_dedup = f'''
CREATE OR REPLACE TABLE `{mx_new_ref}` AS
SELECT o.*
FROM `{mx_staging}` o
WHERE NOT EXISTS (
    SELECT 1 FROM `{PROJECT}.{DATASET}.churches` c
    WHERE LOWER(TRIM(COALESCE(c.name,''))) = LOWER(TRIM(COALESCE(o.name,'')))
      AND LOWER(TRIM(COALESCE(c.state,''))) = LOWER(TRIM(COALESCE(o.state,'')))
      AND c.country = 'MX'
)
'''
job = client.query(sql_mx_dedup, job_config=QueryJobConfig(priority=bigquery.QueryPriority.BATCH))
print('  Deduplicating Mexico...', flush=True)
job.result()
mx_new = list(client.query(f'SELECT COUNT(*) as cnt FROM `{mx_new_ref}`').result())[0].cnt
print(f'  Mexico new: {mx_new:,} ({100*mx_new/mx_total:.1f}% of {mx_total:,})')

# ── Step 3: Download to CSV ──
countries = [('CA', ca_new_ref, 'E:/grid/data/overture_canada_new.csv'),
             ('MX', mx_new_ref, 'E:/grid/data/overture_mexico_new.csv')]

for country_code, bq_ref, csv_path in countries:
    print(f'\n=== Downloading {country_code} to CSV ===')
    rows = list(client.query(f'SELECT * FROM `{bq_ref}`').result())
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['overture_id','name','address','city','state','zip','confidence','latitude','longitude'])
        for r in rows:
            w.writerow([r.overture_id, r.name, r.address, r.city, r.state, r.zip, r.confidence, r.latitude, r.longitude])
    print(f'  Saved {len(rows):,} rows to {csv_path}')

# ── Step 4: Import into SQLite ──
print('\n=== Importing into SQLite ===')
conn = sqlite3.connect('churches.db', timeout=60)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA busy_timeout=60000')

# Load existing index with country
print('  Loading existing index...')
exist = {}
for r in conn.execute("SELECT id, LOWER(COALESCE(name,'')), LOWER(COALESCE(state,'')), COALESCE(country,'US') FROM churches"):
    if r[1] and r[2]:
        exist[(r[1], r[2], r[3])] = r[0]
print(f'  {len(exist):,} existing (name, state, country) pairs')

max_id = conn.execute("SELECT COALESCE(MAX(id), 700000) FROM churches").fetchone()[0]
print(f'  max id: {max_id}')

for country_code, bq_ref, csv_path in countries:
    rows = list(csv.DictReader(open(csv_path, encoding='utf-8')))
    ins = dup = fail = 0
    for i, ch in enumerate(rows):
        name = (ch.get('name') or '').strip()
        state = (ch.get('state') or '').strip()
        key = (name.lower(), state.lower(), country_code)
        
        if not key[0] or not key[1]:
            fail += 1; continue
        
        if key in exist:
            # Log duplicate
            try:
                conn.execute("""INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
                    VALUES (?, 'overture_full', ?, 'duplicate found during overture continent import')""",
                    (exist[key], ch.get('overture_id', '')))
            except: pass
            dup += 1; continue
        
        try:
            lat = float(ch.get('latitude', 0) or 0)
            lon = float(ch.get('longitude', 0) or 0)
            if lat == 0 and lon == 0: fail += 1; continue
        except: fail += 1; continue
        
        max_id += 1
        conn.execute("""
            INSERT INTO churches (id, name, address, city, state, country,
                latitude, longitude, geocode_source, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'overture', 'overture_full')
        """, (max_id, name, ch.get('address','') or '', ch.get('city','') or '',
              state, country_code, lat, lon))
        exist[key] = max_id
        ins += 1
        
        if i % 10000 == 9999:
            conn.commit()
            print(f'  {country_code}: {i+1:,}/{len(rows):,} | {ins:,} ins, {dup:,} dup', flush=True)
    
    conn.commit()
    print(f'  {country_code} DONE: {ins:,} ins, {dup:,} dup, {fail:,} fail')

# ── Step 5: Summary ──
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
ca_db = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
mx_db = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX'").fetchone()[0]
us_db = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]
neither = total - ca_db - mx_db - us_db
print(f'\n=== CONTINENTAL SUMMARY ===')
print(f'  US: {us_db:,}')
print(f'  Canada: {ca_db:,}')
print(f'  Mexico: {mx_db:,}')
print(f'  Other/Null: {neither:,}')
print(f'  TOTAL: {total:,}')

conn.close()
print('Done.')

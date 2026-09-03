"""Extract LDS meetinghouses from Overture - take 2"""
import os, json, tempfile
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
from google.cloud.bigquery import LoadJobConfig, SchemaField

client = bigquery.Client(project='american-rel-infra')

# Query 1: Count church_cathedral with LDS keywords
sql = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
  AND (LOWER(names.primary) LIKE '%ward%' 
       OR LOWER(names.primary) LIKE '%latter%'
       OR LOWER(names.primary) LIKE '%stake%')
'''
try:
    for r in client.query(sql).result():
        print(f'Church_cathedral with LDS keywords (US): {r.cnt:,}')
except Exception as e:
    print(f'Error: {str(e)[:150]}')

# Query 2: Sample to see what fields are available
sql2 = '''
SELECT id, names.primary as name, 
       categories.primary as cat,
       brand.names.primary as brand_name,
       confidence
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -114.1 AND -109.0
  AND bbox.ymin BETWEEN 39.5 AND 42.0
  AND (LOWER(names.primary) LIKE '%ward%' OR LOWER(names.primary) LIKE '%stake%')
LIMIT 10
'''
print('\n=== Utah LDS samples ===')
try:
    for r in client.query(sql2).result():
        print(f'  {r.name[:55]:55s}  brand={r.brand_name or "?"}  conf={r.confidence}  addrs={r.addr_count}')
except Exception as e:
    print(f'Error: {str(e)[:150]}')

# Query 3: Count ALL church_cathedral in US
sql3 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
'''
try:
    for r in client.query(sql3).result():
        print(f'\nTotal church_cathedral (US): {r.cnt:,}')
except Exception as e:
    print(f'Error: {str(e)[:150]}')

# Query 4: Extract to our BQ dataset
print('\n=== Extracting to our dataset ===')
sql4 = '''
SELECT 
    id AS overture_id,
    names.primary AS name,
    addresses.list[SAFE_OFFSET(0)].element.freeform AS address,
    addresses.list[SAFE_OFFSET(0)].element.locality AS city,
    addresses.list[SAFE_OFFSET(0)].element.region AS state,
    addresses.list[SAFE_OFFSET(0)].element.postcode AS zip,
    brand.names.primary AS brand_name,
    categories.primary AS category,
    confidence,
    ST_Y(geometry) AS latitude,
    ST_X(geometry) AS longitude
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
  AND (
      LOWER(names.primary) LIKE '%ward%' 
      OR LOWER(names.primary) LIKE '%stake%'
      OR LOWER(names.primary) LIKE '%latter%'
      OR LOWER(names.primary) LIKE '%lds%'
      OR LOWER(COALESCE(brand.names.primary, '')) LIKE '%latter%'
      OR LOWER(COALESCE(brand.names.primary, '')) LIKE '%mormon%'
  )
'''

try:
    rows = list(client.query(sql4).result())
    print(f'  Found: {len(rows):,} LDS meetinghouses')
    
    if rows:
        # Show samples
        print('\n  First 10:')
        for r in rows[:10]:
            print(f'    {r.name[:50]:50s}  {r.city or "?"}, {r.state or "?"}  ({r.latitude}, {r.longitude})')
        
        # Write to BQ
        table_ref = 'american-rel-infra.American_Religious_Infrastructure.overture_lds_meetinghouses'
        
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
        for r in rows:
            tmp.write(json.dumps({
                'overture_id': r.overture_id,
                'name': r.name,
                'address': r.address,
                'city': r.city,
                'state': r.state,
                'zip': r.zip,
                'brand_name': r.brand_name,
                'category': r.category,
                'confidence': r.confidence,
                'latitude': r.latitude,
                'longitude': r.longitude,
            }) + '\n')
        tmp.close()
        
        client.delete_table(table_ref, not_found_ok=True)
        
        schema = [
            SchemaField('overture_id', 'STRING'),
            SchemaField('name', 'STRING'),
            SchemaField('address', 'STRING'),
            SchemaField('city', 'STRING'),
            SchemaField('state', 'STRING'),
            SchemaField('zip', 'STRING'),
            SchemaField('brand_name', 'STRING'),
            SchemaField('category', 'STRING'),
            SchemaField('confidence', 'FLOAT64'),
            SchemaField('latitude', 'FLOAT64'),
            SchemaField('longitude', 'FLOAT64'),
        ]
        config = LoadJobConfig(schema=schema, source_format='NEWLINE_DELIMITED_JSON', write_disposition='WRITE_TRUNCATE')
        with open(tmp.name, 'rb') as f:
            job = client.load_table_from_file(f, table_ref, job_config=config)
        job.result()
        os.unlink(tmp.name)
        print(f'\n  Written to: {table_ref}')
        print(f'  Rows: {len(rows):,}')
        
except Exception as e:
    print(f'Error: {str(e)[:200]}')

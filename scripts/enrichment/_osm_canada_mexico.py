"""Check Overture Maps coverage for Canada and Mexico places of worship"""
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')

# Check Canada (bbox roughly: -141 to -52 lon, 41 to 83 lat)
print('=== CANADA: church_cathedral in Overture ===')
sql_ca = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -141.0 AND -52.0
  AND bbox.ymin BETWEEN 41.0 AND 83.0
  AND names.primary IS NOT NULL
  AND names.primary != ''
'''
try:
    for r in client.query(sql_ca).result():
        print(f'  Canada church_cathedral: {r.cnt:,}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# Check Mexico (bbox roughly: -118 to -86 lon, 14 to 33 lat)
print('\n=== MEXICO: church_cathedral in Overture ===')
sql_mx = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -118.0 AND -86.0
  AND bbox.ymin BETWEEN 14.0 AND 33.0
  AND names.primary IS NOT NULL
  AND names.primary != ''
'''
try:
    for r in client.query(sql_mx).result():
        print(f'  Mexico church_cathedral: {r.cnt:,}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# Sample Canadian churches
print('\n=== CANADA SAMPLES ===')
sql_ca_sample = '''
SELECT names.primary as name,
       addresses.list[SAFE_OFFSET(0)].element.locality AS city,
       addresses.list[SAFE_OFFSET(0)].element.region AS state,
       ST_Y(geometry) as lat, ST_X(geometry) as lon
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -141.0 AND -52.0
  AND bbox.ymin BETWEEN 41.0 AND 83.0
  AND names.primary IS NOT NULL
LIMIT 12
'''
try:
    for r in client.query(sql_ca_sample).result():
        print(f'  {r.name[:50]:50s}  {r.city or "?":15s} {r.state or "?"}  ({r.lat:.4f}, {r.lon:.4f})')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# Sample Mexican churches
print('\n=== MEXICO SAMPLES ===')
sql_mx_sample = '''
SELECT names.primary as name,
       addresses.list[SAFE_OFFSET(0)].element.locality AS city,
       addresses.list[SAFE_OFFSET(0)].element.region AS state,
       ST_Y(geometry) as lat, ST_X(geometry) as lon
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -118.0 AND -86.0
  AND bbox.ymin BETWEEN 14.0 AND 33.0
  AND names.primary IS NOT NULL
LIMIT 12
'''
try:
    for r in client.query(sql_mx_sample).result():
        print(f'  {r.name[:50]:50s}  {r.city or "?":15s} {r.state or "?"}  ({r.lat:.4f}, {r.lon:.4f})')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# Province/state breakdown for Canada
print('\n=== CANADA BY PROVINCE ===')
sql_ca_prov = '''
SELECT addresses.list[SAFE_OFFSET(0)].element.region AS province, COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -141.0 AND -52.0
  AND bbox.ymin BETWEEN 41.0 AND 83.0
  AND names.primary IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 15
'''
try:
    for r in client.query(sql_ca_prov).result():
        print(f'  {r.province or "?":10s} {r.cnt:>8,}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# Mexico by state
print('\n=== MEXICO BY STATE ===')
sql_mx_state = '''
SELECT addresses.list[SAFE_OFFSET(0)].element.region AS state, COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -118.0 AND -86.0
  AND bbox.ymin BETWEEN 14.0 AND 33.0
  AND names.primary IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC
LIMIT 15
'''
try:
    for r in client.query(sql_mx_state).result():
        print(f'  {r.state or "?":20s} {r.cnt:>8,}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

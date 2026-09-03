import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

print('=== OVERTURE MAPS: LDS/PLACE_OF_WORSHIP IN UTAH ===')

# Query 1: All places of worship in Overture Maps for Utah
sql1 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -114.1 AND -109.0
  AND bbox.ymin BETWEEN 37.0 AND 42.0
'''
try:
    for r in client.query(sql1).result():
        print(f'Total places of worship in Utah bbox: {r.cnt:,}')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Query 2: Sample with names to check for LDS
sql2 = '''
SELECT id, 
       names.value as name,
       categories,
       ST_Y(geometry) as lat,
       ST_X(geometry) as lon
FROM `bigquery-public-data.overture_maps.place`,
     UNNEST(names) as names
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -114.1 AND -109.0
  AND bbox.ymin BETWEEN 37.0 AND 42.0
  AND names.primary = true
  AND (LOWER(names.value) LIKE '%latter%' OR LOWER(names.value) LIKE '%mormon%' OR LOWER(names.value) LIKE '%lds%')
LIMIT 10
'''
try:
    rows = list(client.query(sql2).result())
    print(f'\nLDS-tagged places of worship: {len(rows)} in first 10 results')
    for r in rows:
        cats = [c.get('primary','') for c in (r.categories or [])] if r.categories else []
        print(f'  {r.name[:50]:50s}  lat={r.lat}  lon={r.lon}  cats={cats[:3]}')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Query 3: ALL places of worship with "ward" in name (LDS organizational unit)
sql3 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`,
     UNNEST(names) as names
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -114.1 AND -109.0
  AND bbox.ymin BETWEEN 37.0 AND 42.0
  AND names.primary = true
  AND LOWER(names.value) LIKE '%ward%'
'''
try:
    for r in client.query(sql3).result():
        print(f'\nPlaces with "ward" in name (Utah): {r.cnt:,}')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Query 4: Total places of worship in Juab County bbox
sql4 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -112.2 AND -111.7
  AND bbox.ymin BETWEEN 39.5 AND 39.9
'''
try:
    for r in client.query(sql4).result():
        print(f'\nPlaces of worship in Juab County: {r.cnt}')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Query 5: Sample of Juab County places of worship
sql5 = '''
SELECT names.value as name,
       ST_Y(geometry) as lat,
       ST_X(geometry) as lon
FROM `bigquery-public-data.overture_maps.place`,
     UNNEST(names) as names
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -112.2 AND -111.7
  AND bbox.ymin BETWEEN 39.5 AND 39.9
  AND names.primary = true
LIMIT 15
'''
try:
    rows = list(client.query(sql5).result())
    print(f'\nJuab County places of worship sample:')
    for r in rows:
        print(f'  {r.name[:50]:50s}  lat={r.lat}  lon={r.lon}')
    if not rows:
        print('  NONE FOUND')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Query 6: How many overture places of worship total in the US?
sql6 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'place_of_worship'
'''
try:
    for r in client.query(sql6).result():
        print(f'\nTotal Overture places of worship (US): {r.cnt:,}')
except Exception as e:
    print(f'Error: {str(e)[:200]}')

# Compare: how many did we capture from overture?
import sqlite3
conn = sqlite3.connect('churches.db')
ov_total = conn.execute("SELECT COUNT(*) FROM churches WHERE source IN ('overture','overture_discovery')").fetchone()[0]
ov_ut = conn.execute("SELECT COUNT(*) FROM churches WHERE source IN ('overture','overture_discovery') AND state='UT'").fetchone()[0]
print(f'\nOur DB: {ov_total:,} from overture total, {ov_ut} in Utah')
conn.close()

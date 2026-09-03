"""Extract ALL LDS meetinghouses from Overture Maps - nationwide US"""
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')

# First, check the schema of the place table
print('=== Overture place table schema ===')
t = client.get_table('bigquery-public-data.overture_maps.place')
for s in t.schema[:15]:
    print(f'  {s.name:30s} {s.field_type:20s} {s.mode or ""}')
print(f'  ... ({len(t.schema)} columns total)')

# The categories field is likely: categories.primary = 'place_of_worship'
# names might be a REPEATED STRUCT now

# Try simple count first - no UNNEST
print('\n=== Testing basic queries ===')

# Query 1: Simple count by bbox
sql1 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'religious'
LIMIT 1
'''
try:
    for r in client.query(sql1).result():
        print(f'  categories.primary=religious: {r.cnt}')
except Exception as e:
    print(f'  religious: {str(e)[:80]}')

# Query 2: Try place_of_worship  
sql2 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'place_of_worship'
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
'''
try:
    for r in client.query(sql2).result():
        print(f'  place_of_worship in US bbox: {r.cnt:,}')
except Exception as e:
    print(f'  pow: {str(e)[:120]}')

# Query 3: Try categories.alternate (array of structs)
sql3 = '''
SELECT COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE 'place_of_worship' IN UNNEST(categories.alternate)
  AND bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
LIMIT 1
'''
try:
    for r in client.query(sql3).result():
        print(f'  alternate[place_of_worship]: {r.cnt:,}')
except Exception as e:
    print(f'  alternate: {str(e)[:120]}')

# Query 4: What primary categories exist?
print('\n=== Top categories ===')
sql4 = '''
SELECT categories.primary as cat, COUNT(*) as cnt
FROM `bigquery-public-data.overture_maps.place`
WHERE bbox.xmin BETWEEN -125.0 AND -65.0
  AND bbox.ymin BETWEEN 24.0 AND 50.0
GROUP BY 1
ORDER BY 2 DESC
LIMIT 20
'''
try:
    for r in client.query(sql4).result():
        print(f'  {r.cat or "(null)":30s} {r.cnt:>12,}')
except Exception as e:
    print(f'  categories: {str(e)[:120]}')

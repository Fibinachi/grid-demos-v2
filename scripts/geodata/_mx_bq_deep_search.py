"""Search for INEGI data in BigQuery public datasets more broadly"""
from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

# Search across ALL public datasets for INEGI / Mexico census references
q1 = """
SELECT table_catalog, table_schema, table_name, table_type
FROM `bigquery-public-data.INFORMATION_SCHEMA.TABLES`
WHERE table_name LIKE '%inegi%'
   OR table_name LIKE '%mexico%'
   OR table_name LIKE '%ageb%'
   OR table_name LIKE '%censo%'
ORDER BY table_catalog, table_schema, table_name
"""
print('=== INEGI/Mexico tables in bigquery-public-data ===')
try:
    for row in client.query(q1).result():
        print(f'  {row.table_catalog}.{row.table_schema}.{row.table_name} ({row.table_type})')
except Exception as e:
    print(f'  Error: {str(e)[:120]}')

# Check cartobq project 
q2 = """
SELECT table_catalog, table_schema, table_name, table_type
FROM `cartobq.INFORMATION_SCHEMA.TABLES`
WHERE table_name LIKE '%mexico%'
   OR table_name LIKE '%inegi%'
   OR table_name LIKE '%ageb%'
ORDER BY table_name
"""
print('\n=== INEGI/Mexico tables in cartobq ===')
try:
    for row in client.query(q2).result():
        print(f'  {row.table_catalog}.{row.table_schema}.{row.table_name} ({row.table_type})')
except Exception as e:
    print(f'  Error: {str(e)[:120]}')

# Check Overture for division_area with CVEGEO-like attributes
q3 = """
SELECT column_name, data_type
FROM `bigquery-public-data.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'division_area'
  AND table_schema = 'overture_maps'
ORDER BY ordinal_position
"""
print('\n=== Overture division_area columns ===')
try:
    for row in client.query(q3).result():
        print(f'  {row.column_name}: {row.data_type}')
except Exception as e:
    print(f'  Error: {str(e)[:120]}')

"""Check Overture division_area for Mexico - actual boundary polygons"""
from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

# Check division_area subtypes for MX
q1 = """
SELECT subtype, class, admin_level, COUNT(*) as cnt
FROM bigquery-public-data.overture_maps.division_area
WHERE country = 'MX'
GROUP BY subtype, class, admin_level
ORDER BY admin_level
"""
print('=== Overture division_area MX subtypes ===')
for row in client.query(q1).result():
    al = str(row.admin_level).rjust(3) if row.admin_level is not None else 'None'
    st = str(row.subtype).ljust(20)
    cl = str(row['class']).ljust(20) if row['class'] else 'None'.ljust(20)
    ct = str(row.cnt).rjust(8)
    print(f'  admin_level={al} | {st} | {cl} | {ct}')

# Check if Overture has any admin_level 3 (something between municipio and locality)
q2 = """
SELECT DISTINCT admin_level, subtype
FROM bigquery-public-data.overture_maps.division
WHERE country = 'MX' AND admin_level IS NOT NULL
ORDER BY admin_level
"""
print('\n=== Distinct admin_level in Overture MX ===')
for row in client.query(q2).result():
    print(f'  admin_level={row.admin_level}: {row.subtype}')

# Check what's in geo_international or similar datasets
q3 = """
SELECT table_id, table_type, table_name
FROM `bigquery-public-data.INFORMATION_SCHEMA.TABLES`
WHERE table_catalog = 'bigquery-public-data'
  AND table_schema = 'geo_international'
"""
print('\n=== bigquery-public-data.geo_international tables ===')
try:
    for row in client.query(q3).result():
        print(f'  {row.table_id}')
except:
    print('  Table not found or no permission')

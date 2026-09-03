"""Check Overture Mexico admin levels"""
from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

q = """
SELECT admin_level, subtype, class, COUNT(*) as cnt
FROM bigquery-public-data.overture_maps.division
WHERE country = 'MX'
GROUP BY admin_level, subtype, class
ORDER BY admin_level
"""
for row in client.query(q).result():
    al = str(row.admin_level).rjust(3)
    st = str(row.subtype).ljust(20)
    cl = str(row['class']).ljust(20)
    ct = str(row.cnt).rjust(8)
    print(f'  admin_level={al} | {st} | {cl} | {ct}')

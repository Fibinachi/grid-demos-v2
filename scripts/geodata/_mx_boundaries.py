"""Find Mexican admin boundaries in Overture + cartobq"""
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery
client = bigquery.Client(project='american-rel-infra')

print('=== Overture division table ===')
for tbl_name in ['division', 'division_area']:
    try:
        t = client.get_table(f'bigquery-public-data.overture_maps.{tbl_name}')
        print(f'{tbl_name}: {t.num_rows} rows, {len(t.schema)} cols')
        for s in t.schema[:10]:
            print(f'  {s.name}: {s.field_type}')
    except Exception as e:
        print(f'{tbl_name}: {str(e)[:120]}')

print('\n=== Overture division Mexico ===')
try:
    for r in client.query("SELECT COUNT(*) as cnt FROM bigquery-public-data.overture_maps.division WHERE country = 'MX'").result():
        print(f'  Mexico divisions: {r.cnt:,}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

print('\n=== cartobq datasets with Mexico/geo ===')
try:
    for ds in client.list_datasets(project='cartobq', max_results=200):
        did = ds.dataset_id.lower()
        if any(x in did for x in ['mexico','inegi','censo','ageb','geo','admin','boundary']):
            print(f'  cartobq.{ds.dataset_id}')
            for t in client.list_tables(f'cartobq.{ds.dataset_id}'):
                tbl = client.get_table(f'cartobq.{ds.dataset_id}.{t.table_id}')
                print(f'    {t.table_id}: {tbl.num_rows} rows')
except Exception as e:
    print(f'  Error: {str(e)[:100]}')

# Check Google Open Buildings for MX
print('\n=== Google Open Buildings Mexico ===')
try:
    for r in client.query("SELECT COUNT(*) as cnt FROM bigquery-public-data.google_buildings_open.buildings WHERE bbox.xmin BETWEEN -118 AND -86 AND bbox.ymin BETWEEN 14 AND 33 LIMIT 1").result():
        print(f'  Buildings in Mexico bbox: {r.cnt}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

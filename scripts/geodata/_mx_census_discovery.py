"""Discover Mexican census data in BigQuery"""
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')

# Search for Mexican datasets
print('=== Searching for INEGI / Mexico datasets ===')
for proj in ['bigquery-public-data']:
    try:
        for ds in client.list_datasets(project=proj, max_results=1000):
            did = ds.dataset_id.lower()
            if any(x in did for x in ['mexico', 'inegi', 'censo', 'ageb', 'geo_mx']):
                print(f'\n  {proj}.{ds.dataset_id}')
                for t in client.list_tables(f'{proj}.{ds.dataset_id}'):
                    tbl = client.get_table(f'{proj}.{ds.dataset_id}.{t.table_id}')
                    print(f'    {t.table_id}: {tbl.num_rows} rows, {len(tbl.schema)} cols')
                    for s in tbl.schema[:8]:
                        print(f'      {s.name}: {s.field_type}')
    except Exception as e:
        print(f'  Error listing {proj}: {str(e)[:100]}')

# Also try specific known INEGI datasets
print('\n=== Trying known INEGI paths ===')
known = [
    'bigquery-public-data.geo_mexico',
    'bigquery-public-data.census_mexico',
    'bigquery-public-data.inegi',
    'bigquery-public-data.mexico_census',
    'bigquery-public-data.geo_international',
]
for path in known:
    try:
        ds = client.get_dataset(path)
        print(f'  FOUND: {path}')
        for t in client.list_tables(path):
            tbl = client.get_table(f'{path}.{t.table_id}')
            print(f'    {t.table_id}: {tbl.num_rows} rows')
            for s in tbl.schema[:6]:
                print(f'      {s.name}: {s.field_type}')
    except Exception as e:
        if 'Not found' in str(e):
            print(f'  NOT FOUND: {path}')
        else:
            print(f'  {path}: {str(e)[:100]}')

# Check geo_international for Mexico
print('\n=== geo_international contents ===')
try:
    for ds in client.list_datasets(project='bigquery-public-data', max_results=2000):
        if 'international' in ds.dataset_id.lower() or 'geo' in ds.dataset_id.lower():
            if 'mexico' in ds.dataset_id.lower() or 'world' in ds.dataset_id.lower():
                print(f'  {ds.dataset_id}')
                for t in client.list_tables(f'bigquery-public-data.{ds.dataset_id}'):
                    print(f'    {t.table_id}')
except:
    pass

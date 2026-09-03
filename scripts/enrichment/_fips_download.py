import os, sqlite3
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')
result_ref = 'american-rel-infra.American_Religious_Infrastructure._fips_backfill_result'

print('Downloading results...')
results = list(client.query(f'SELECT * FROM `{result_ref}`').result())
print(f'{len(results):,} rows')

conn = sqlite3.connect('churches.db', timeout=60)
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA busy_timeout=60000')

updated = 0
batch = []
for r in results:
    batch.append((r.county_fips, r.county_name, int(r.id)))
    if len(batch) >= 10000:
        conn.executemany('UPDATE churches SET county_fips=?, county_name=? WHERE id=?', batch)
        updated += len(batch)
        print(f'  {updated:,}...', flush=True)
        batch = []
        conn.commit()

if batch:
    conn.executemany('UPDATE churches SET county_fips=?, county_name=? WHERE id=?', batch)
    updated += len(batch)
    conn.commit()

print(f'Updated: {updated:,}')

remaining = conn.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND (county_fips IS NULL OR county_fips = '')").fetchone()[0]
print(f'Remaining without FIPS: {remaining:,}')

juab = conn.execute("SELECT COUNT(*) FROM churches WHERE county_fips='49023'").fetchone()[0]
print(f'\nJuab County: {juab} churches')
for r in conn.execute("SELECT name, city, source FROM churches WHERE county_fips='49023' LIMIT 10").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} ({r[2]})')

conn.close()
print('Done.')

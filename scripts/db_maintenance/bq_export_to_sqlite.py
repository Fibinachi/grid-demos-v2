"""Export BigQuery churches table to SQLite — RESUMABLE, no ORDER BY"""
from google.cloud import bigquery
import sqlite3, os, time, sys

client = bigquery.Client(project='american-rel-infra')
BQ_TABLE = 'American_Religious_Infrastructure.churches'
SQLITE_DB = 'churches.db'

# Step 1: Get schema from BQ
print('Getting schema from BigQuery...')
table = client.get_table(BQ_TABLE)
bq_cols = [field.name for field in table.schema]
print(f'{len(bq_cols)} columns in BQ')

# Step 2: Get existing columns in SQLite
db = sqlite3.connect(SQLITE_DB, timeout=300)
c = db.cursor()
c.execute('PRAGMA table_info(churches)')
sqlite_cols = [r[1] for r in c.fetchall()]
print(f'{len(sqlite_cols)} columns in SQLite churches table')

# Map BQ columns to SQLite columns (only columns that exist in SQLite)
matching_cols = [col for col in bq_cols if col in sqlite_cols]
missing_in_sqlite = [col for col in bq_cols if col not in sqlite_cols]
print(f'Matching: {len(matching_cols)}')
if missing_in_sqlite:
    print(f'Missing in SQLite: {len(missing_in_sqlite)} - {missing_in_sqlite[:10]}...')

BATCH_SIZE = 5000

col_quoted = ', '.join(f'`{c}`' for c in matching_cols)
col_sqlite = ', '.join(f'"{c}"' for c in matching_cols)
ph = ', '.join(['?'] * len(matching_cols))

# Step 3: Check existing bq_churches table (resume support)
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bq_churches'")
bq_table_exists = c.fetchone() is not None

if bq_table_exists:
    c.execute('SELECT COUNT(*) FROM bq_churches')
    existing = c.fetchone()[0]
    print(f'\nbq_churches already has {existing:,} rows — RESUMING')
    offset = existing
else:
    print('\nCreating fresh bq_churches table...')
    c.execute('DROP TABLE IF EXISTS bq_churches')
    c.execute(f'CREATE TABLE bq_churches AS SELECT * FROM churches WHERE 1=0')
    db.commit()
    existing = 0
    offset = 0

# Step 4: Get total from BQ
total = client.query(f'SELECT COUNT(*) FROM {BQ_TABLE}').result()
total_rows = list(total)[0][0]
print(f'BQ total: {total_rows:,} | Local: {existing:,} | Remaining: {total_rows - existing:,}')
print(f'Exporting in batches of {BATCH_SIZE} (NO ORDER BY for speed)...')

added = 0
failed_batches = 0
t0 = time.time()
last_report = offset

while offset < total_rows:
    # NO ORDER BY — much faster, and order doesn't matter for recovery
    q = f'SELECT {col_quoted} FROM {BQ_TABLE} LIMIT {BATCH_SIZE} OFFSET {offset}'
    try:
        rows = list(client.query(q).result())
    except Exception as e:
        failed_batches += 1
        print(f'  Query error at offset {offset:,}: {e}', flush=True)
        offset += BATCH_SIZE
        if failed_batches > 10:
            print('Too many failures, aborting.', flush=True)
            break
        continue
    
    if not rows:
        break
    
    batch_added = 0
    for row in rows:
        vals = [row.get(col) for col in matching_cols]
        try:
            c.execute(f'INSERT INTO bq_churches ({col_sqlite}) VALUES ({ph})', vals)
            added += 1
            batch_added += 1
        except Exception:
            pass
    
    db.commit()
    offset += len(rows)
    
    if offset - last_report >= 50000 or offset >= total_rows:
        elapsed = time.time() - t0
        rate = (offset - existing) / elapsed if elapsed > 0 else 0
        pct = offset / total_rows * 100
        eta = (total_rows - offset) / rate if rate > 0 else 0
        print(f'  {offset:,}/{total_rows:,} ({pct:.1f}%) | {rate:.0f} rows/s | ETA {eta/60:.0f}min | {existing + added:,} in DB', flush=True)
        last_report = offset

elapsed = time.time() - t0
print(f'\n=== EXPORT COMPLETE ===')
print(f'Exported: {added:,} new rows in {elapsed:.0f}s ({added/elapsed:.0f} rows/s)')
print(f'Failed batches: {failed_batches}')

# Verify
c.execute('SELECT COUNT(*) FROM bq_churches')
final_count = c.fetchone()[0]
print(f'bq_churches total: {final_count:,}')
c.execute("SELECT COUNT(*) FROM bq_churches WHERE website IS NOT NULL AND website != ''")
print(f'Websites: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM bq_churches WHERE email IS NOT NULL AND email != ''")
print(f'Emails: {c.fetchone()[0]:,}')

# Integrity check
c.execute('PRAGMA integrity_check')
print(f'Integrity: {c.fetchone()[0]}')

db.close()
print('\nDone! bq_churches table is ready. Run verify_and_swap.py to replace main churches table.')

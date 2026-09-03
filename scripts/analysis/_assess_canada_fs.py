#!/usr/bin/env python3
"""Filesystem and infrastructure check for Canadian geocoding."""

import sqlite3, os

db = sqlite3.connect(r'E:\grid\churches.db')

# Check churches columns
cur = db.execute("SELECT name FROM pragma_table_info('churches')")
all_cols = [r[0] for r in cur.fetchall()]
print(f'churches columns: {all_cols}')

# Check census_zip_data
cur = db.execute("SELECT name FROM pragma_table_info('census_zip_data')")
print(f'\ncensus_zip_data columns: {[r[0] for r in cur.fetchall()]}')
cur = db.execute('SELECT COUNT(*) FROM census_zip_data')
print(f'census_zip_data rows: {cur.fetchone()[0]}')

# Fix the earlier query - find address-related columns
for c in all_cols:
    if 'address' in c.lower() or 'street' in c.lower() or 'post' in c.lower() or 'zip' in c.lower() or 'addr' in c.lower():
        print(f'  Address-related column: {c}')

# Check natural_earth db
ne_path = r'E:\grid\data\natural_earth\world_borders.db'
if os.path.exists(ne_path):
    nedb = sqlite3.connect(ne_path)
    cur = nedb.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print(f'\nworld_borders.db tables: {[r[0] for r in cur.fetchall()]}')
    nedb.close()
else:
    print(f'\nworld_borders.db NOT FOUND')
    os.makedirs(r'E:\grid\data\natural_earth', exist_ok=True)

# Check data directory structure
data_dir = r'E:\grid\data'
if os.path.exists(data_dir):
    print(f'\n=== data/ directory contents ===')
    for item in sorted(os.listdir(data_dir)):
        full = os.path.join(data_dir, item)
        if os.path.isdir(full):
            subs = os.listdir(full) if os.path.exists(full) else []
            size = len(subs)
            print(f'  📁 {item}/ ({size} items)')
        else:
            size = os.path.getsize(full)
            print(f'  📄 {item} ({size:,} bytes)')

db.close()

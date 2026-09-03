"""
Rename census tables to consistent naming convention:
  church_acs          → church_census_us
  church_canada_census → church_census_ca
  church_mexico_census → church_census_mx
  county_acs           → county_census_us
  mx_municipio_census  → municipio_census_mx
  tract_fips_lookup    → tract_lookup_us
"""
import sqlite3

DB = r'E:\grid\churches.db'
RENAMES = [
    ('church_acs',           'church_census_us'),
    ('church_canada_census', 'church_census_ca'),
    ('church_mexico_census', 'church_census_mx'),
    ('county_acs',           'county_census_us'),
    ('mx_municipio_census',  'municipio_census_mx'),
    ('tract_fips_lookup',    'tract_lookup_us'),
]

db = sqlite3.connect(DB)
db.execute('PRAGMA foreign_keys = OFF')

for old, new in RENAMES:
    # Check if old exists and new doesn't
    exists = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (old,)).fetchone()[0]
    already = db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (new,)).fetchone()[0]
    if not exists:
        print(f'SKIP {old} → {new}  (old table not found)')
        continue
    if already:
        print(f'SKIP {old} → {new}  (new name already exists)')
        continue
    db.execute(f'ALTER TABLE [{old}] RENAME TO [{new}]')
    # Also rename associated indexes
    idxs = db.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (new,)).fetchall()
    for (idx,) in idxs:
        if old in idx:
            new_idx = idx.replace(old, new)
            db.execute(f'DROP INDEX [{idx}]')
            print(f'  DROPPED index {idx} (re-create with scripts later)')
    row_count = db.execute(f'SELECT COUNT(*) FROM [{new}]').fetchone()[0]
    print(f'OK   {old} → {new}  ({row_count:,} rows)')

db.commit()
db.execute('PRAGMA foreign_keys = ON')
db.close()
print('\nDone. Verify with: .schema church_census_*')

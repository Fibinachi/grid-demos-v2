"""Survey exactly what demographic data exists and how it's structured."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')
c = db.cursor()

# 1. Full church_enrichment schema
print('=== church_enrichment FULL schema ===')
cols = c.execute('PRAGMA table_info(church_enrichment)').fetchall()
for row in cols:
    print(f'  {row[1]:35s} {row[2]:20s} nullable={row[3]} default={row[4]}')

# 2. Sample row to see patterns
print('\n=== Sample church_enrichment row (first 5) ===')
for n in range(5):
    row = c.execute(f'SELECT * FROM church_enrichment LIMIT 1 OFFSET {n}').fetchone()
    if row:
        col_names = [r[1] for r in cols]
        print(f'\n--- Row {n} ---')
        for name, val in zip(col_names, row):
            if val is not None and val != '' and val != 0:
                print(f'  {name:35s} = {val}')

# 3. Churches table FIPS column
print('\n=== churches table (FIPS columns) ===')
for col in ['fips', 'zip', 'zip5', 'country']:
    cnt = c.execute(f'SELECT COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != ""').fetchone()[0]
    print(f'  {col}: {cnt:,}')

# 4. tract_fips in church_enrichment
tcnt = c.execute('SELECT COUNT(*) FROM church_enrichment WHERE tract_fips IS NOT NULL AND tract_fips != ""').fetchone()[0]
print(f'\n  tract_fips in enrichment: {tcnt:,}')

# 5. county_fips
fcnt = c.execute('SELECT COUNT(*) FROM church_enrichment WHERE county_fips IS NOT NULL AND county_fips != ""').fetchone()[0]
print(f'  county_fips in enrichment: {fcnt:,}')

# 6. Election data non-null counts
print('\n=== Election data coverage ===')
for col in ['dem_share_2020', 'rep_share_2020', 'total_ballots_2020', 'turnout_rate_2020',
            'dem_share_2024', 'turnout_rate_2024']:
    cnt = c.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE {col} IS NOT NULL AND {col} > 0').fetchone()[0]
    print(f'  {col}: {cnt:,}')

# 7. ARDA data coverage
print('\n=== ARDA coverage ===')
for col in ['members_arda', 'attendance_arda']:
    cnt = c.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE {col} IS NOT NULL AND {col} > 0').fetchone()[0]
    print(f'  {col}: {cnt:,}')

# 8. County demographic columns - what's populated?
print('\n=== County demographic columns ===')
demo_cols = [r[1] for r in cols if r[1].startswith('county_')]
demo_cols_total = len(demo_cols)
populated = 0
for col in demo_cols:
    cnt = c.execute(f'SELECT COUNT(*) FROM church_enrichment WHERE {col} IS NOT NULL AND {col} != "" AND {col} != 0').fetchone()[0]
    if cnt > 0:
        populated += 1
        print(f'  {col}: {cnt:,}')
if populated == 0:
    print('  (all empty — no county demographic data merged yet)')
print(f'  --- {populated}/{demo_cols_total} columns populated ---')

# 9. Provenance log
print('\n=== Provenance log (last 10 entries) ===')
try:
    for row in c.execute('SELECT * FROM provenance_log ORDER BY id DESC LIMIT 10').fetchall():
        print(f'  id={row[0]} source={row[1]} action={row[2]} timestamp={row[3]}')
except:
    print('  No provenance_log or different schema')

# 10. Check church_geographies
print('\n=== Existing geography tables ===')
for tbl in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
    print(f'  {tbl[0]}')

# 11. Unique county FIPS values
print('\n=== How many unique county FIPS? ===')
fcnt = c.execute('SELECT COUNT(DISTINCT county_fips) FROM church_enrichment WHERE county_fips IS NOT NULL AND county_fips != ""').fetchone()[0]
print(f'  Unique county FIPS in enrichment: {fcnt}')

# 12. election data - how many unique geographies?
print('\n=== How many unique election geographies? ===')
# election data seems to be by county_fips -> need to check if it's matched by county
fcnt = c.execute('SELECT COUNT(*) FROM (SELECT DISTINCT county_fips FROM church_enrichment WHERE dem_share_2020 IS NOT NULL)').fetchone()[0]
print(f'  Unique counties with 2020 election data: {fcnt}')

db.close()
print('\nDone!')

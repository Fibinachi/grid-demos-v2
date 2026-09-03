import sqlite3
db = sqlite3.connect(r'E:\grid\churches.db')
c = db.cursor()

tables = ['election_results', 'county_fips_lookup', 'tract_lookup_us', 
          'census_zip_data', 'arda_county_data', 'church_census_us', 'church_arda',
          'church_geographies', 'church_enrichment']

for tbl in tables:
    try:
        cnt = c.execute(f"SELECT COUNT(*) FROM \"{tbl}\"").fetchone()[0]
        cols = c.execute(f"PRAGMA table_info(\"{tbl}\")").fetchall()
        print(f'=== {tbl} ({cnt:,} rows) ===')
        for col in cols:
            print(f'  {col[0]:3d} {col[1]:30s} {col[2]:15s} nullable={col[3]} default={col[4]}')
        print()
    except Exception as e:
        print(f'=== {tbl}: {e} ===\n')

# Also list all indices on these tables
print('=== Useful indices ===')
for tbl in tables:
    try:
        for row in c.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{tbl}'").fetchall():
            print(f'  {tbl}.{row[0]}')
    except:
        pass

db.close()
print('Done!')

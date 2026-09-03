import sqlite3, json, os
conn = sqlite3.connect('churches.db')

# NRHP stats
nrhp = conn.execute("SELECT COUNT(*) FROM churches WHERE nrhp_ref IS NOT NULL AND nrhp_ref != ''").fetchone()[0]
# GNIS stats
gnis = conn.execute("SELECT COUNT(*) FROM churches WHERE gnis_feature_id IS NOT NULL AND gnis_feature_id != ''").fetchone()[0]
# Denom by classification method
name_cls = conn.execute("SELECT COUNT(*) FROM churches WHERE classification_source='name_heuristic'").fetchone()[0]
irs_cls = conn.execute("SELECT COUNT(*) FROM churches WHERE classification_source='irs_ntee'").fetchone()[0]
# Check what geo columns exist
cols = [r[1] for r in conn.execute("PRAGMA table_info(churches)").fetchall()]
geo_cols = [c for c in cols if any(x in c.lower() for x in ['cbsa','rucc','dma','gnis','nrhp','classif'])]
print(f'Geo/enrich columns: {geo_cols}')

# Table inventory
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print(f'NRHP historic churches: {nrhp:,}')
print(f'GNIS feature IDs: {gnis:,}')
print(f'Name-classified denom: {name_cls:,}')
print(f'IRS NTEE-classified: {irs_cls:,}')
pass
print(f'\nTotal tables in DB: {len(tables)}')
print('Key tables (>100 rows):')
for t in tables:
    try:
        cnt = conn.execute(f'SELECT COUNT(*) FROM "{t[0]}"').fetchone()[0]
        if cnt > 100:
            print(f'  {t[0]:35s} {cnt:>10,}')
    except:
        pass

# ChurchUnion scraper
ck = 'data/churchunion_checkpoint.json'
if os.path.exists(ck):
    d = json.load(open(ck))
    print(f'\nChurchUnion scraper: {d["total_scraped"]:,} churches from {d["last_page"]:,}/{d["total_pages"]:,} pages ({100*d["last_page"]/d["total_pages"]:.1f}%)')

# BQ export table
print('\nBQ export: american-rel-infra.American_Religious_Infrastructure.churches')

# Data dir size
import subprocess
result = subprocess.run(['powershell', '-Command', '(Get-ChildItem -Path E:\\grid\\data -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB'], capture_output=True, text=True)
print(f'data/ directory: {float(result.stdout.strip()):.0f} MB')

conn.close()

"""
Fill US ZIP codes via Census ZCTA spatial join.
For each US church with GPS but no ZIP, find the ZCTA polygon that contains it.

Download first:
  wsl curl -L -o data/tl_2024_us_zcta520.zip \
    'https://www2.census.gov/geo/tiger/TIGER2024/ZCTA520/tl_2024_us_zcta520.zip'

Usage:
  python scripts/enrichment/fill_zip_zcta.py          # process all
  python scripts/enrichment/fill_zip_zcta.py --dry-run # test 10 samples
  python scripts/enrichment/fill_zip_zcta.py --limit 1000
"""
import sqlite3, os, sys, time, zipfile, tempfile, shutil
from tqdm import tqdm

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, 'churches.db')
ZCTA_ZIP = os.path.join(ROOT, 'data', 'tl_2024_us_zcta520.zip')

DRY_RUN = '--dry-run' in sys.argv
LIMIT = None
for i, a in enumerate(sys.argv):
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a == '--limit' and i + 1 < len(sys.argv):
        try: LIMIT = int(sys.argv[i + 1])
        except ValueError: pass

print("Loading ZCTA shapefile...")
import geopandas as gpd
from shapely.geometry import Point
from shapely.strtree import STRtree

# Extract ZCTA to temp dir
tmpdir = tempfile.mkdtemp()
with zipfile.ZipFile(ZCTA_ZIP) as zf:
    zf.extractall(tmpdir)
shp_path = None
for f in os.listdir(tmpdir):
    if f.endswith('.shp'):
        shp_path = os.path.join(tmpdir, f)
        break

print(f"  Shapefile: {shp_path}")
gdf = gpd.read_file(shp_path, engine='pyogrio')
print(f"  {len(gdf):,} ZCTAs loaded")

zcta_col = 'ZCTA5CE20'
geoms = gdf.geometry.tolist()
zcta_codes = gdf[zcta_col].tolist()

print("Building spatial index...")
tree = STRtree(geoms)
print(f"  Done.")

# Clean up temp
shutil.rmtree(tmpdir, ignore_errors=True)

# Connect to DB
con = sqlite3.connect(DB)
con.execute("PRAGMA journal_mode=WAL")
cur = con.cursor()

# Fetch ALL US churches with GPS (overwrite any bad ZIPs with authoritative ZCTA)
sql = """SELECT id, latitude, longitude, zip FROM churches
         WHERE country='US' AND latitude IS NOT NULL AND latitude != 0 AND latitude != ''
         AND longitude IS NOT NULL AND longitude != 0 AND longitude != ''
         ORDER BY id"""
if LIMIT:
    sql += f' LIMIT {LIMIT}'

cur.execute(sql)
rows = cur.fetchall()
total = len(rows)
print(f"\nUS churches (all, for ZIP accuracy): {total:,}")

if DRY_RUN:
    print("DRY RUN — testing 10 samples...")
    rows = rows[:10]
    total = len(rows)
    for chid, lat, lon, old_zip in rows:
        pt = Point(lon, lat)
        idx = tree.query(pt, predicate='intersects')
        if len(idx):
            zcta = zcta_codes[idx[0]]
            changed = " (CHANGED)" if old_zip != zcta else ""
            print(f"  [{chid}] ({lat:.5f},{lon:.5f}) old={old_zip} -> new={zcta}{changed}")
        else:
            print(f"  [{chid}] ({lat:.5f},{lon:.5f}) old={old_zip} -> NO ZCTA")
    con.close()
    sys.exit(0)

# Process
CHUNK = 500
batch = []
filled = 0
corrected = 0
missed = 0
start = time.time()

for chid, lat, lon, old_zip in tqdm(rows, desc="ZIP spatial join", unit='rec'):
    pt = Point(lon, lat)
    idx = tree.query(pt, predicate='intersects')
    if len(idx):
        zcta = zcta_codes[idx[0]]
        if old_zip != zcta:
            batch.append((zcta, chid))
            if old_zip:
                corrected += 1
            else:
                filled += 1
    else:
        missed += 1
        if missed <= 5:
            tqdm.write(f"  [{chid}] ({lat:.5f},{lon:.5f}) -> NO ZCTA")

    if len(batch) >= CHUNK:
        cur.executemany("UPDATE churches SET zip=? WHERE id=?", batch)
        con.commit()
        batch = []

if batch:
    cur.executemany("UPDATE churches SET zip=? WHERE id=?", batch)
    con.commit()

elapsed = time.time() - start
print(f"\nDone in {elapsed:.0f}s")
print(f"  Filled (was empty):  {filled:,}")
print(f"  Corrected (was wrong): {corrected:,}")
print(f"  Unchanged (was right): {total - filled - corrected - missed:,}")
print(f"  Missed (no ZCTA):    {missed:,}")
print(f"  Rate:    {total/elapsed:.0f} rec/s")

# Verify
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND latitude!=0 AND (zip IS NULL OR zip='')")
remaining = cur.fetchone()[0]
print(f"  Remaining US without ZIP: {remaining:,}")

con.close()

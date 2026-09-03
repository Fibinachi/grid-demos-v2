"""Italy ADM1: download geoBoundaries, spatial join, create church_election_IT, backfill admin1."""
import sqlite3, json, urllib.request, ssl, time
from datetime import datetime
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

fname = DATA_DIR / 'gb_IT_ADM1.geojson'
if not fname.exists():
    api_url = 'https://www.geoboundaries.org/api/current/gbOpen/ITA/ADM1/'
    req = urllib.request.Request(api_url, headers={'User-Agent': 'GRID/1.0'})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        meta = json.loads(r.read())
    dl_url = meta['gjDownloadURL']
    print(f'Downloading...')
    req = urllib.request.Request(dl_url, headers={'User-Agent': 'GRID/1.0'})
    with urllib.request.urlopen(req, timeout=300, context=ctx) as r:
        with open(fname, 'wb') as f:
            f.write(r.read())
    print(f'Downloaded: {fname.stat().st_size/1024/1024:.1f} MB')
else:
    print(f'Already have: {fname.name}')

print('Loading GeoJSON...')
gdf = gpd.read_file(fname)
print(f'{len(gdf)} features, cols: {list(gdf.columns)[:5]}')

db = sqlite3.connect(DB, timeout=120)
db.execute('PRAGMA journal_mode=WAL')
c = db.cursor()

c.execute("SELECT rowid, id, latitude, longitude FROM churches WHERE country='IT' AND latitude IS NOT NULL")
church_rows = c.fetchall()
print(f'{len(church_rows):,} churches with GPS')

church_gdf = gpd.GeoDataFrame(
    [(r[0], r[1]) for r in church_rows],
    columns=['rowid', 'id'],
    geometry=[Point(lon, lat) for _, _, lat, lon in church_rows],
    crs='EPSG:4326'
)

if gdf.crs is None:
    gdf = gdf.set_crs('EPSG:4326')
elif gdf.crs != 'EPSG:4326':
    gdf = gdf.to_crs('EPSG:4326')

print('Spatial join...')
t0 = time.time()
joined = gpd.sjoin(church_gdf, gdf[['shapeID', 'shapeName', 'geometry']], how='inner', predicate='within')
print(f'{len(joined):,} matched in {time.time()-t0:.1f}s')

now = datetime.now().isoformat()
sd = now[:10]

c.execute('''CREATE TABLE IF NOT EXISTS church_election_IT (
    church_rowid INTEGER PRIMARY KEY, dist_code TEXT, dist_name TEXT, source TEXT, source_date TEXT)''')
c.execute('DELETE FROM church_election_IT')

rows = [(int(r['rowid']), str(r['shapeID']), str(r['shapeName']),
         'geoBoundaries ADM1 - Italy region = Senate constituency', sd)
        for _, r in joined.iterrows()]

for i in range(0, len(rows), CHUNK):
    c.executemany('INSERT OR REPLACE INTO church_election_IT VALUES (?,?,?,?,?)', rows[i:i+CHUNK])

# Backfill churches
updates = [(r[2], r[1], r[0]) for r in rows]
for i in range(0, len(updates), CHUNK):
    c.executemany("UPDATE churches SET admin1_name=?, admin1_code=? WHERE rowid=? AND (admin1_code IS NULL OR admin1_code = '')", updates[i:i+CHUNK])

db.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE country='IT' AND admin1_code IS NOT NULL AND admin1_code != ''")
adm1_count = c.fetchone()[0]
total = c.execute("SELECT COUNT(*) FROM churches WHERE country='IT'").fetchone()[0]
print(f'Backfill: {adm1_count:,}/{total:,} ({adm1_count/total*100:.0f}%)')

c.execute('''INSERT OR REPLACE INTO church_census_catalog 
    (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
    VALUES (?, ?, 'election', ?, ?, 3, ?, ?, ?)''',
    ('IT', 'church_election_IT', 'ADM1 region', 'geoBoundaries ADM1 - Italy region = Senate constituency', len(rows), sd, now))
db.commit()
db.close()

# Provenance
db2 = sqlite3.connect(DB)
db2.execute('''INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, fields_populated, records_attempted, status)
    VALUES (?,?,?,?,?,?,?,?)''',
    ('geoBoundaries', 'italy_adm1.py', now, now, len(rows), 'admin1_code,admin1_name', len(rows), 'completed'))
db2.commit()
db2.close()
print('Done.')

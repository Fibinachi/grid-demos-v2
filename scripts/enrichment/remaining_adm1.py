"""Remaining ADM1 backfill: AU (from existing election) + IT (new geoBoundaries ADM1)."""
import sqlite3
import json
import urllib.request
import ssl
import time
from datetime import datetime
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

def backfill_from_election(db, iso):
    """Backfill admin1_code/name from existing church_election table."""
    c = db.cursor()
    table = f'church_election_{iso}'
    
    c.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not c.fetchone()[0]:
        print(f'  {table}: MISSING')
        return 0
    
    c.execute(f"SELECT COUNT(*) FROM churches WHERE country='{iso}' AND (admin1_code IS NULL OR admin1_code = '')")
    null_count = c.fetchone()[0]
    if null_count == 0:
        print(f'  {iso}: already has admin1_code')
        return 0
    
    print(f'  {iso}: {null_count:,} need backfill')
    
    c.execute(f"""
        SELECT ce.church_rowid, ce.dist_code, ce.dist_name
        FROM {table} ce
        JOIN churches c ON c.rowid = ce.church_rowid
        WHERE c.country = '{iso}'
          AND (c.admin1_code IS NULL OR c.admin1_code = '')
    """)
    rows = c.fetchall()
    print(f'  {len(rows):,} matches in {table}')
    
    if not rows:
        return 0
    
    for i in range(0, len(rows), CHUNK):
        batch = [(r[1], r[2], r[0]) for r in rows[i:i+CHUNK]]
        c.executemany('UPDATE churches SET admin1_code=?, admin1_name=? WHERE rowid=?', batch)
    
    db.commit()
    print(f'  {iso}: {len(rows):,} updated')
    return len(rows)


def create_election_italy(db):
    """Download IT ADM1 from geoBoundaries, spatial join, create table + backfill."""
    iso = 'IT'
    iso3 = 'ITA'
    cfg = {'name': 'Italy', 'desc': 'Region = Senate constituency'}
    
    c = db.cursor()
    cnt = c.execute('SELECT COUNT(*) FROM churches WHERE country=?', (iso,)).fetchone()[0]
    print(f'\n  {iso} - {cfg["name"]} ({cnt:,} churches)')
    
    # Download
    fname = DATA_DIR / f'gb_{iso}_ADM1.geojson'
    if not fname.exists():
        api_url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/'
        print(f'    Fetching metadata...', end=' ', flush=True)
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
                meta = json.loads(r.read())
        except Exception as e:
            print(f'FAILED: {e}')
            return 0
        
        dl_url = meta.get('gjDownloadURL')
        if not dl_url:
            print('No download URL')
            return 0
        
        print(f'downloading ({meta.get("boundaryName","?")})...', end=' ', flush=True)
        try:
            req = urllib.request.Request(dl_url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as r:
                with open(fname, 'wb') as f:
                    f.write(r.read())
            size_mb = fname.stat().st_size / (1024*1024)
            print(f'{size_mb:.1f} MB')
        except Exception as e:
            print(f'FAILED: {e}')
            return 0
    else:
        print(f'    Already downloaded: {fname.name}')
    
    # Load GeoJSON
    print(f'    Loading GeoJSON...', end=' ', flush=True)
    gdf = gpd.read_file(fname)
    print(f'{len(gdf)} features')
    
    id_col = 'shapeID'
    name_col = 'shapeName'
    if id_col not in gdf.columns:
        for col in gdf.columns:
            cl = col.lower()
            if 'shapeid' in cl: id_col = col
            if 'shapename' in cl: name_col = col
    if name_col not in gdf.columns:
        name_col = gdf.columns[1] if len(gdf.columns) > 1 else gdf.columns[0]
    
    print(f'    ID col: {id_col}, Name col: {name_col}')
    
    # Load churches
    c.execute(f"SELECT rowid, id, name, latitude, longitude FROM churches WHERE country='{iso}' AND latitude IS NOT NULL")
    church_rows = c.fetchall()
    print(f'    {len(church_rows):,} churches with GPS')
    
    # Spatial join
    church_gdf = gpd.GeoDataFrame(
        [(r[0], r[1]) for r in church_rows],
        columns=['rowid', 'id'],
        geometry=[Point(lon, lat) for _, _, _, lat, lon in church_rows],
        crs='EPSG:4326'
    )
    
    if gdf.crs is None:
        gdf = gdf.set_crs('EPSG:4326')
    elif gdf.crs != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')
    
    print(f'    Spatial join...', end=' ', flush=True)
    t0 = time.time()
    joined = gpd.sjoin(church_gdf, gdf[[id_col, name_col, 'geometry']], how='inner', predicate='within')
    elapsed = time.time() - t0
    print(f'{len(joined):,} matched in {elapsed:.1f}s')
    
    # Create election table
    table = 'church_election_IT'
    now = datetime.now().isoformat()
    source_date = now[:10]
    
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            church_rowid INTEGER PRIMARY KEY,
            dist_code TEXT,
            dist_name TEXT,
            source TEXT,
            source_date TEXT
        )
    """)
    c.execute(f'DELETE FROM {table}')
    
    rows = [(int(r['rowid']), str(r[id_col]), str(r[name_col]),
             f'geoBoundaries ADM1 - {cfg["desc"]}', source_date)
            for _, r in joined.iterrows()]
    
    for i in range(0, len(rows), CHUNK):
        c.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', rows[i:i+CHUNK])
    
    # Backfill churches
    updates = [(r[2], r[1], r[0]) for r in rows]  # name, code, rowid
    for i in range(0, len(updates), CHUNK):
        c.executemany(
            'UPDATE churches SET admin1_name=?, admin1_code=? WHERE rowid=? AND (admin1_code IS NULL OR admin1_code = "")',
            updates[i:i+CHUNK]
        )
    
    db.commit()
    
    # Catalog
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', ?, ?, 3, ?, ?, ?)
    """, (iso, table, 'ADM1 region', f'geoBoundaries ADM1 - {cfg["desc"]}', len(rows), source_date, now))
    db.commit()
    
    pct = 100 * len(rows) / cnt if cnt else 0
    print(f'    -> church_election_IT: {len(rows):,} rows ({pct:.0f}%)')
    return len(rows)


def main():
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    print("=" * 60)
    print("AU: Backfill from existing church_election_AU")
    print("=" * 60)
    au_count = backfill_from_election(db, 'AU')
    
    print("\n" + "=" * 60)
    print("IT: Create church_election_IT + backfill")
    print("=" * 60)
    it_count = create_election_italy(db)
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: AU={au_count:,} + IT={it_count:,} = {au_count+it_count:,} total")
    
    # Provenance
    db2 = sqlite3.connect(DB)
    now = datetime.now().isoformat()
    db2.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('geoBoundaries', 'remaining_adm1.py', now, now,
          au_count + it_count, 'admin1_code,admin1_name',
          au_count + it_count, 'completed'))
    db2.commit()
    db2.close()

if __name__ == '__main__':
    main()

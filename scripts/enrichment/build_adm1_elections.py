"""Check ADM1 level and build election tables for province=district countries."""
import sqlite3, json, urllib.request, ssl, time
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

# Countries where ADM1 = electoral district
COUNTRIES = {
    'ES': {'iso3': 'ESP', 'name': 'Spain', 'desc': 'Province = Congress constituency'},
    'TR': {'iso3': 'TUR', 'name': 'Turkey', 'desc': 'Province = electoral district'},
    'ZA': {'iso3': 'ZAF', 'name': 'South Africa', 'desc': 'Province = PR constituency'},
    'BE': {'iso3': 'BEL', 'name': 'Belgium', 'desc': 'Province = Chamber constituency'},
    'AR': {'iso3': 'ARG', 'name': 'Argentina', 'desc': 'Province = diputados district'},
    'PE': {'iso3': 'PER', 'name': 'Peru', 'desc': 'Department = electoral district'},
    'CH': {'iso3': 'CHE', 'name': 'Switzerland', 'desc': 'Canton = constituency'},
    'DK': {'iso3': 'DNK', 'name': 'Denmark', 'desc': 'Region = multi-member district'},
    'NO': {'iso3': 'NOR', 'name': 'Norway', 'desc': 'Fylke = constituency'},
    'CO': {'iso3': 'COL', 'name': 'Colombia', 'desc': 'Department = constituency'},
    'EC': {'iso3': 'ECU', 'name': 'Ecuador', 'desc': 'Province = constituency'},
    'GT': {'iso3': 'GTM', 'name': 'Guatemala', 'desc': 'Department = constituency'},
    'AT': {'iso3': 'AUT', 'name': 'Austria', 'desc': 'Land = electoral region'},
    'CZ': {'iso3': 'CZE', 'name': 'Czechia', 'desc': 'Kraj = constituency'},
    'HR': {'iso3': 'HRV', 'name': 'Croatia', 'desc': 'County = electoral district'},
    'PT': {'iso3': 'PRT', 'name': 'Portugal', 'desc': 'District = constituency'},
}

def download_adm1(iso, iso3):
    """Download ADM1 GeoJSON from geoBoundaries."""
    fname = DATA_DIR / f'gb_{iso}_ADM1.geojson'
    if fname.exists():
        print(f'  Already downloaded: {fname.name}')
        return fname
    
    api_url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/'
    print(f'  Fetching metadata...', end=' ', flush=True)
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
            meta = json.loads(r.read())
    except Exception as e:
        print(f'FAILED: {e}')
        return None
    
    dl_url = meta.get('gjDownloadURL')
    if not dl_url:
        print('No download URL')
        return None
    
    print(f'downloading ({meta.get("boundaryName","?")})...', end=' ', flush=True)
    try:
        req = urllib.request.Request(dl_url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as r:
            with open(fname, 'wb') as f:
                f.write(r.read())
        size_mb = fname.stat().st_size / (1024*1024)
        print(f'{size_mb:.1f} MB')
        return fname
    except Exception as e:
        print(f'FAILED: {e}')
        return None

def spatial_join_country(db, iso, cfg, geojson_path):
    """Spatial join churches to ADM1 boundaries."""
    print(f'  Loading GeoJSON...', end=' ', flush=True)
    gdf = gpd.read_file(geojson_path)
    print(f'{len(gdf)} features')
    
    # Find ID and name columns
    id_col = None
    name_col = None
    for col in gdf.columns:
        cl = col.lower()
        if id_col is None and ('shapeid' in cl or 'shape_id' in cl or 'adm1_id' in cl or 'id' == cl):
            id_col = col
        if name_col is None and ('shapename' in cl or 'shape_name' in cl or 'shape' in cl and 'name' in cl or 'name' == cl):
            name_col = col
    if id_col is None:
        id_col = gdf.columns[0]
    if name_col is None:
        name_col = gdf.columns[1] if len(gdf.columns) > 1 else gdf.columns[0]
    
    print(f'  ID col: {id_col}, Name col: {name_col}')
    
    # Load churches
    c = db.cursor()
    c.execute(f"SELECT rowid, id, name, latitude, longitude FROM churches WHERE country='{iso}' AND latitude IS NOT NULL")
    church_rows = c.fetchall()
    print(f'  {len(church_rows):,} churches with GPS')
    
    if not church_rows:
        return 0
    
    # Build GeoDataFrame
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
    
    # Spatial join
    print(f'  Spatial join...', end=' ', flush=True)
    t0 = time.time()
    joined = gpd.sjoin(church_gdf, gdf[[id_col, name_col, 'geometry']], how='inner', predicate='within')
    elapsed = time.time() - t0
    print(f'{len(joined):,} matched in {elapsed:.1f}s')
    
    # Create table
    table = f'church_election_{iso}'
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
    
    # Batch insert
    rows = []
    for _, row in joined.iterrows():
        rows.append((
            int(row['rowid']),
            str(row[id_col]) if hasattr(row, id_col) else '',
            str(row[name_col]) if hasattr(row, name_col) else '',
            f'geoBoundaries ADM1 — {cfg["desc"]}',
            source_date
        ))
    
    for i in range(0, len(rows), CHUNK):
        c.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', rows[i:i+CHUNK])
    
    db.commit()
    
    # Catalog
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', ?, ?, 3, ?, ?, ?)
    """, (iso, table, 'ADM1 province', f'geoBoundaries ADM1 — {cfg["desc"]}', len(rows), source_date, now))
    db.commit()
    
    return len(rows)


def main():
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    total = 0
    for iso, cfg in COUNTRIES.items():
        c = db.cursor()
        cnt = c.execute('SELECT COUNT(*) FROM churches WHERE country=?', (iso,)).fetchone()[0]
        print(f'\n{"="*60}')
        print(f'{iso} — {cfg["name"]} ({cnt:,} churches)')
        print(f'{"="*60}')
        
        # Download ADM1
        fname = download_adm1(iso, cfg['iso3'])
        if not fname:
            continue
        
        # Spatial join
        matched = spatial_join_country(db, iso, cfg, fname)
        if matched:
            pct = 100 * matched / cnt if cnt else 0
            print(f'  -> church_election_{iso}: {matched:,} rows ({pct:.0f}%)')
            total += matched
    
    db.close()
    print(f'\n{"="*60}')
    print(f'DONE: {total:,} churches enriched across election tables')
    
    # Provenance
    db2 = sqlite3.connect(DB)
    now = datetime.now().isoformat()
    db2.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES ('world_election_adm1', 'build_adm1_elections.py', ?, ?, ?, 'election_district', ?, 'completed')
    """, (now, datetime.now().isoformat(), total, total))
    db2.commit()
    db2.close()

if __name__ == '__main__':
    main()

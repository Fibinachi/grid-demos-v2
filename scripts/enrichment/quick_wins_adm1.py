"""Quick Wins: ADM1 backfill + election boundaries for KR,TR,TW,AT,PL,RU,UA.

Part 1: Backfill admin1_code/name from existing church_election tables (KR,TR,TW,AT)
Part 2: Create church_election tables via geoBoundaries ADM1 (PL,RU,UA)
"""
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

# ── Part 1: ADM1 Backfill from existing church_election tables ──

def backfill_adm1_from_election(db, iso):
    """Read church_election_{iso} and populate churches.admin1_code/name."""
    c = db.cursor()
    
    # Check if table exists
    table = f'church_election_{iso}'
    c.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='{table}'")
    if not c.fetchone()[0]:
        print(f'  {table}: MISSING, skipping')
        return 0
    
    # Check current state
    c.execute(f"SELECT COUNT(*) FROM churches WHERE country='{iso}' AND (admin1_code IS NULL OR admin1_code = '')")
    null_count = c.fetchone()[0]
    if null_count == 0:
        print(f'  {iso}: already has admin1_code for all churches, skipping')
        return 0
    
    print(f'  {iso}: {null_count:,} churches need admin1_code backfill')
    
    # Read from election table
    c.execute(f"""
        SELECT ce.church_rowid, ce.dist_code, ce.dist_name, c.rowid
        FROM {table} ce
        JOIN churches c ON c.rowid = ce.church_rowid
        WHERE c.country = '{iso}'
          AND (c.admin1_code IS NULL OR c.admin1_code = '')
    """)
    rows = c.fetchall()
    print(f'  {len(rows):,} matches found in {table}')
    
    if not rows:
        return 0
    
    # Batch update
    updates = []
    for church_rowid, dist_code, dist_name, c_rowid in rows:
        updates.append((dist_code, dist_name, c_rowid))
    
    for i in range(0, len(updates), CHUNK):
        batch = updates[i:i+CHUNK]
        c.executemany(
            'UPDATE churches SET admin1_code=?, admin1_name=? WHERE rowid=?',
            batch
        )
    
    db.commit()
    print(f'  {iso}: ✅ {len(updates):,} churches updated with admin1_code/name')
    return len(updates)


# ── Part 2: Create election tables for PL, RU, UA ──

NEW_COUNTRIES = {
    'PL': {'iso3': 'POL', 'name': 'Poland', 'desc': 'Voivodeship = Senate constituency'},
    'RU': {'iso3': 'RUS', 'name': 'Russia', 'desc': 'Federal Subject = electoral district'},
    'UA': {'iso3': 'UKR', 'name': 'Ukraine', 'desc': 'Oblast = electoral district'},
}

def download_adm1(iso, iso3):
    """Download ADM1 GeoJSON from geoBoundaries."""
    fname = DATA_DIR / f'gb_{iso}_ADM1.geojson'
    if fname.exists():
        print(f'    Already downloaded: {fname.name}')
        return fname
    
    api_url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/'
    print(f'    Fetching metadata...', end=' ', flush=True)
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
    """Spatial join churches to ADM1 boundaries, create church_election table + backfill."""
    print(f'    Loading GeoJSON...', end=' ', flush=True)
    gdf = gpd.read_file(geojson_path)
    print(f'{len(gdf)} features')
    
    # Find ID and name columns
    id_col = None
    name_col = None
    for col in gdf.columns:
        cl = col.lower()
        if id_col is None and ('shapeid' in cl or 'shape_id' in cl or 'adm1_id' in cl or 'id' == cl):
            id_col = col
        if name_col is None and ('shapename' in cl or 'shape_name' in cl or ('shape' in cl and 'name' in cl) or 'name' == cl):
            name_col = col
    if id_col is None:
        id_col = gdf.columns[0]
    if name_col is None:
        name_col = gdf.columns[1] if len(gdf.columns) > 1 else gdf.columns[0]
    
    print(f'    ID col: {id_col}, Name col: {name_col}')
    
    # Load churches
    c = db.cursor()
    c.execute(f"SELECT rowid, id, name, latitude, longitude FROM churches WHERE country='{iso}' AND latitude IS NOT NULL")
    church_rows = c.fetchall()
    print(f'    {len(church_rows):,} churches with GPS')
    
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
    print(f'    Spatial join...', end=' ', flush=True)
    t0 = time.time()
    joined = gpd.sjoin(church_gdf, gdf[[id_col, name_col, 'geometry']], how='inner', predicate='within')
    elapsed = time.time() - t0
    print(f'{len(joined):,} matched in {elapsed:.1f}s')
    
    # Create election table
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
    
    # Batch insert to election table
    rows = []
    for _, row in joined.iterrows():
        rows.append((
            int(row['rowid']),
            str(row[id_col]),
            str(row[name_col]),
            f'geoBoundaries ADM1 - {cfg["desc"]}',
            source_date
        ))
    
    for i in range(0, len(rows), CHUNK):
        c.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', rows[i:i+CHUNK])
    
    # ALSO backfill churches.admin1_code/name
    admin1_updates = [(str(row[name_col]), str(row[id_col]), int(row['rowid'])) for _, row in joined.iterrows()]
    for i in range(0, len(admin1_updates), CHUNK):
        c.executemany(
            'UPDATE churches SET admin1_name=?, admin1_code=? WHERE rowid=? AND (admin1_code IS NULL OR admin1_code = "")',
            admin1_updates[i:i+CHUNK]
        )
    
    db.commit()
    
    # Catalog
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', ?, ?, 3, ?, ?, ?)
    """, (iso, table, 'ADM1 province', f'geoBoundaries ADM1 - {cfg["desc"]}', len(rows), source_date, now))
    db.commit()
    
    return len(rows)


# ── Main ──

def main():
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    total_backfill = 0
    total_election = 0
    
    # ── Part 1: Backfill KR, TR, TW, AT ──
    print("=" * 60)
    print("PART 1: ADM1 Backfill from existing church_election tables")
    print("=" * 60)
    for iso in ['KR', 'TR', 'TW', 'AT']:
        n = backfill_adm1_from_election(db, iso)
        total_backfill += n
    
    # ── Part 2: Create election tables for PL, RU, UA ──
    print("\n" + "=" * 60)
    print("PART 2: Create election tables for PL, RU, UA")
    print("=" * 60)
    for iso, cfg in NEW_COUNTRIES.items():
        c = db.cursor()
        cnt = c.execute('SELECT COUNT(*) FROM churches WHERE country=?', (iso,)).fetchone()[0]
        print(f'\n  {iso} - {cfg["name"]} ({cnt:,} churches)')
        
        # Download ADM1
        fname = download_adm1(iso, cfg['iso3'])
        if not fname:
            continue
        
        # Spatial join + create table + backfill
        matched = spatial_join_country(db, iso, cfg, fname)
        if matched:
            pct = 100 * matched / cnt if cnt else 0
            print(f'    -> church_election_{iso}: {matched:,} rows ({pct:.0f}%)')
            total_election += matched
    
    db.close()
    
    # ── Summary ──
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  ADM1 backfill (KR,TR,TW,AT): {total_backfill:,} churches")
    print(f"  Election tables (PL,RU,UA): {total_election:,} churches")
    print(f"  TOTAL: {total_backfill + total_election:,}")
    
    # Provenance
    db2 = sqlite3.connect(DB)
    now = datetime.now().isoformat()
    db2.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('geoBoundaries', 'quick_wins_adm1.py', now, now,
          total_backfill + total_election, 'admin1_code,admin1_name',
          total_backfill + total_election, 'completed'))
    db2.commit()
    db2.close()
    print("  Provenance logged.")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Unified census + election import for 13 mature democracies missing coverage.

Census (ADM1 geoBoundaries): AU, GB, FI, IS, IL, LU
Election (ADM1 or electoral boundaries): IE, JP, NL, NZ, KR, SE, TW, FI, IS, IL, LU

Creates: church_census_{ISO2} + church_election_{ISO2} tables
Registers in: church_census_catalog

Estimated: ~20 min for all 13 countries
"""

import sqlite3
import json
import ssl
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

# ── Config ──────────────────────────────────────────────────────────

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── Country Registry ────────────────────────────────────────────────
# (iso2, iso3, name, needs_census, needs_election, election_note)

COUNTRIES = {
    'AU': {'iso3': 'AUS', 'name': 'Australia',       'census': True,  'election': False, 'note': 'Already has church_election_AU'},
    'GB': {'iso3': 'GBR', 'name': 'United Kingdom',   'census': True,  'election': False, 'note': 'Already has church_election_GB'},
    'IE': {'iso3': 'IRL', 'name': 'Ireland',          'census': False, 'election': True,  'note': 'ADM1 counties (not Dáil constituencies)'},
    'JP': {'iso3': 'JPN', 'name': 'Japan',            'census': False, 'election': True,  'note': 'ADM1 prefectures (not HR districts)'},
    'NL': {'iso3': 'NLD', 'name': 'Netherlands',      'census': False, 'election': True,  'note': 'ADM1 provinces'},
    'NZ': {'iso3': 'NZL', 'name': 'New Zealand',      'census': False, 'election': True,  'note': 'ADM1 regions (not Maori/general electorates)'},
    'KR': {'iso3': 'KOR', 'name': 'South Korea',      'census': False, 'election': True,  'note': 'ADM1 provinces'},
    'SE': {'iso3': 'SWE', 'name': 'Sweden',           'census': False, 'election': True,  'note': 'ADM1 län (not Riksdag constituencies)'},
    'TW': {'iso3': 'TWN', 'name': 'Taiwan',           'census': False, 'election': True,  'note': 'ADM1 counties/cities'},
    'FI': {'iso3': 'FIN', 'name': 'Finland',          'census': True,  'election': True,  'note': 'ADM1 maakunta'},
    'IS': {'iso3': 'ISL', 'name': 'Iceland',          'census': True,  'election': True,  'note': 'ADM1 regions'},
    'IL': {'iso3': 'ISR', 'name': 'Israel',           'census': True,  'election': True,  'note': 'ADM1 districts (Knesset = single national)'},
    'LU': {'iso3': 'LUX', 'name': 'Luxembourg',       'census': True,  'election': True,  'note': 'ADM1 cantons'},
}

# ── Helpers ──────────────────────────────────────────────────────────

def progress_bar(done, total, label='', width=40):
    """Simple progress bar string."""
    pct = done / total if total else 0
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    return f'\r{label} [{bar}] {done:,}/{total:,} ({pct*100:.1f}%)'

def log(msg):
    print(f'  [{datetime.now().strftime("%H:%M:%S")}] {msg}')

def download_adm1(iso, iso3):
    """Download ADM1 GeoJSON from geoBoundaries."""
    fname = DATA_DIR / f'gb_{iso}_ADM1.geojson'
    if fname.exists() and fname.stat().st_size > 1000:
        return fname
    
    api_url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM1/'
    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
            meta = json.loads(r.read())
    except Exception as e:
        print(f'    geoBoundaries API failed: {e}')
        return None
    
    dl_url = meta.get('gjDownloadURL')
    if not dl_url:
        print(f'    No download URL in geoBoundaries response')
        return None
    
    print(f'    Downloading {meta.get("boundaryName","?")}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(dl_url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as r:
            data = r.read()
        with open(fname, 'wb') as f:
            f.write(data)
        size_mb = len(data) / (1024*1024)
        print(f'{size_mb:.1f} MB')
        return fname
    except Exception as e:
        print(f'FAILED: {e}')
        return None

def spatial_join_adm1(db, iso, gdf, table_name, category, desc):
    """Spatial join churches → ADM1 districts, create table."""
    c = db.cursor()
    
    # Find id/name columns
    id_col = None
    name_col = None
    for col in gdf.columns:
        low = col.lower()
        if id_col is None and ('shapeid' in low or 'shape_id' in low or 'adm1_id' in low or 'code' in low):
            id_col = col
        if name_col is None and ('shapename' in low or 'shape_name' in low or 'name' in low or 'adm1_nm' in low):
            name_col = col
    
    if id_col is None:
        id_col = gdf.columns[0]
    if name_col is None:
        name_col = gdf.columns[1] if len(gdf.columns) > 1 else gdf.columns[0]
    
    # Load churches with GPS
    c.execute(f"""
        SELECT rowid, latitude, longitude
        FROM churches 
        WHERE country = '{iso}' AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    churches = c.fetchall()
    print(f'    {len(churches):,} churches with GPS')
    
    if not churches:
        print(f'    No GPS churches — skipping')
        return 0
    
    # Build church GeoDataFrame
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': [r[0] for r in churches]},
        geometry=[Point(r[2], r[1]) for r in churches],
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != gdf.crs:
        church_gdf = church_gdf.to_crs(gdf.crs)
    
    # Spatial join
    print(f'    Spatial join...', end=' ', flush=True)
    joined = gpd.sjoin(church_gdf, gdf[[id_col, name_col, 'geometry']], how='left', predicate='within')
    matched = joined[id_col].notna().sum()
    print(f'{matched:,}/{len(joined):,} matched ({100*matched/len(joined):.1f}%)')
    
    # Create table
    c.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name='{table_name}'")
    if c.fetchone()[0]:
        c.execute(f'DROP TABLE {table_name}')
    
    db.executescript(f'''
        CREATE TABLE {table_name} (
            church_rowid    INTEGER PRIMARY KEY,
            dist_code       TEXT,
            dist_name       TEXT,
            source          TEXT DEFAULT '',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX idx_{table_name}_code ON {table_name}(dist_code);
    ''')
    
    # Batch insert
    result = joined[['church_rowid', id_col, name_col]].dropna(subset=[id_col])
    rows = [(int(r.church_rowid), str(getattr(r, id_col)), str(getattr(r, name_col)))
            for r in result.itertuples()]
    
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i+CHUNK]
        db.executemany(
            f'INSERT INTO {table_name} (church_rowid, dist_code, dist_name, source) VALUES (?,?,?,?)',
            [(r[0], r[1], r[2], 'geoBoundaries ADM1') for r in chunk]
        )
        if i % (CHUNK*10) == 0:
            pct = min(100, 100*(i+CHUNK)/len(rows))
            print(f'\r    Writing... {pct:.0f}%', end='', flush=True)
    print(f'\r    Wrote {len(rows):,} rows to {table_name}')
    
    db.commit()
    
    # Register in catalog
    c.execute('''INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, row_count, source_date)
        VALUES (?,?,?,?,?,?,date('now'))''',
        (iso, table_name, category, 'ADM1', desc, len(rows)))
    
    return len(rows)

def hardcode_israel_election(db):
    """Israel has a single national Knesset district — assign all."""
    table = 'church_election_IL'
    c = db.cursor()
    c.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name='{table}'")
    if c.fetchone()[0]:
        c.execute(f'DROP TABLE {table}')
    
    db.executescript(f'''
        CREATE TABLE {table} (
            church_rowid    INTEGER PRIMARY KEY,
            dist_code       TEXT,
            dist_name       TEXT,
            source          TEXT DEFAULT '',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX idx_{table}_code ON {table}(dist_code);
    ''')
    
    c.execute("SELECT rowid FROM churches WHERE country='IL' AND latitude IS NOT NULL")
    churches = [r[0] for r in c.fetchall()]
    
    for i in range(0, len(churches), CHUNK):
        chunk = churches[i:i+CHUNK]
        db.executemany(
            f'INSERT INTO {table} (church_rowid, dist_code, dist_name, source) VALUES (?,?,?,?)',
            [(rid, 'IL-NAT', 'Israel (National District)', 'Single national district') for rid in chunk]
        )
    
    db.commit()
    log(f'  Israel election: {len(churches):,} churches → single national district')
    
    c.execute('''INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, row_count, source_date)
        VALUES (?,?,?,?,?,?,date('now'))''',
        ('IL', table, 'election', 'national', 'Knesset single national district', len(churches)))
    
    return len(churches)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    db = sqlite3.connect(str(DB))
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    
    # Ensure catalog exists
    db.execute('''CREATE TABLE IF NOT EXISTS church_census_catalog (
        country TEXT,
        table_name TEXT UNIQUE,
        category TEXT,
        geo_unit TEXT,
        description TEXT,
        variable_count INTEGER,
        row_count INTEGER,
        source_date TEXT,
        refresh_date TEXT
    )''')
    
    census_countries = [(iso, cfg) for iso, cfg in COUNTRIES.items() if cfg['census']]
    election_countries = [(iso, cfg) for iso, cfg in COUNTRIES.items() if cfg['election']]
    
    print('=' * 65)
    print(f'  CENSUS + ELECTION IMPORT — {len(COUNTRIES)} countries')
    print(f'  Census: {len(census_countries)}  |  Election: {len(election_countries)}')
    print('=' * 65)
    
    # ── Phase 1: Census ADM1 ────────────────────────────────────────
    
    print(f'\n{"─"*65}')
    print(f'  PHASE 1: CENSUS ADM1 ({len(census_countries)} countries)')
    print(f'{"─"*65}')
    
    for idx, (iso, cfg) in enumerate(census_countries):
        name = cfg['name']
        iso3 = cfg['iso3']
        tbl = f'church_census_{iso}'
        desc = f'ADM1 administrative district per church ({name})'
        
        print(f'\n  [{idx+1}/{len(census_countries)}] {iso} {name}')
        
        # Download
        fname = download_adm1(iso, iso3)
        if not fname:
            print(f'    SKIPPED — download failed')
            continue
        
        # Load and join
        gdf = gpd.read_file(fname)
        print(f'    {len(gdf):,} ADM1 features, CRS: {gdf.crs}')
        
        n = spatial_join_adm1(db, iso, gdf, tbl, 'census', desc)
        log(f'  ✓ {name} census: {n:,} churches → {tbl}')
    
    # ── Phase 2: Election ────────────────────────────────────────────
    
    print(f'\n{"─"*65}')
    print(f'  PHASE 2: ELECTION ({len(election_countries)} countries)')
    print(f'{"─"*65}')
    
    for idx, (iso, cfg) in enumerate(election_countries):
        name = cfg['name']
        iso3 = cfg['iso3']
        note = cfg['note']
        tbl = f'church_election_{iso}'
        desc = f'ADM1 electoral district per church ({name}) — {note}'
        
        print(f'\n  [{idx+1}/{len(election_countries)}] {iso} {name}')
        print(f'    Note: {note}')
        
        # Israel special case — single national district
        if iso == 'IL':
            hardcode_israel_election(db)
            continue
        
        # Check if census table already exists — reuse ADM1 boundaries
        census_tbl = f'church_census_{iso}'
        c = db.cursor()
        c.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name='{census_tbl}'")
        has_census = c.fetchone()[0] > 0
        
        if has_census and not cfg.get('census'):
            # Census table was just created in Phase 1, or already existed
            # Reuse ADM1 boundaries for election
            fname = DATA_DIR / f'gb_{iso}_ADM1.geojson'
            if not fname.exists():
                fname = download_adm1(iso, iso3)
                if not fname:
                    print(f'    SKIPPED — no ADM1 data')
                    continue
            
            gdf = gpd.read_file(fname)
            n = spatial_join_adm1(db, iso, gdf, tbl, 'election', desc)
        else:
            # Download ADM1 for election
            fname = download_adm1(iso, iso3)
            if not fname:
                print(f'    SKIPPED — download failed')
                continue
            
            gdf = gpd.read_file(fname)
            print(f'    {len(gdf):,} ADM1 features, CRS: {gdf.crs}')
            n = spatial_join_adm1(db, iso, gdf, tbl, 'election', desc)
        
        log(f'  ✓ {name} election: {n:,} churches → {tbl}')
    
    # ── Summary ──────────────────────────────────────────────────────
    
    elapsed = time.time() - t0
    print(f'\n{"="*65}')
    print(f'  COMPLETE — {elapsed/60:.1f} min')
    
    # Verify
    c = db.cursor()
    c.execute('''SELECT category, COUNT(DISTINCT country) FROM church_census_catalog 
        WHERE category IN ('census','election') GROUP BY category''')
    for cat, cnt in c.fetchall():
        print(f'  {cat}: {cnt} countries total')
    
    db.close()

if __name__ == '__main__':
    main()

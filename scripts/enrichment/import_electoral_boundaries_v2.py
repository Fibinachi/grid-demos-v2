#!/usr/bin/env python3
"""
Download electoral district boundaries from ArcGIS FeatureServers and other stable APIs.
Spatial joins churches to actual electoral districts (replacing ADM1 approximations).

Usage:
    python scripts/enrichment/import_electoral_boundaries_v2.py
"""

import json, sqlite3, ssl, sys, time, urllib.request
from datetime import datetime
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


# ── Data Sources ─────────────────────────────────────────────────────
# Using ArcGIS FeatureServers where available (stable, versioned APIs)
# Fallback: government open data portals with direct download URLs

SOURCES = {
    # ── ArcGIS FeatureServers ──
    'DE': {
        'name': 'Germany Bundestag wahlkreise (299)',
        'type': 'arcgis',
        'url': 'https://services2.arcgis.com/jUpNdisbWqRpMo35/arcgis/rest/services/Wahlergebnisse_2025_Wahlkreise/FeatureServer/0',
        'id_col': 'WKR_NR',
        'name_col': 'WKR_NAME',
        'table': 'church_election_DE',
        'geo_unit': 'wahlkreis',
        'description': 'Bundestag constituency 2025 per church',
    },
    # ── Direct GeoJSON downloads ──
    'IE': {
        'name': 'Ireland Dáil constituencies (43)',
        'type': 'direct',
        'url': 'https://raw.githubusercontent.com/rdmolony/dail-constituencies/main/dail-constituencies.geojson',
        'id_col': 'Constituency',
        'name_col': 'Constituency',
        'table': 'church_election_IE',
        'geo_unit': 'constituency',
        'description': 'Dáil Éireann constituency (2024) per church',
        'fallback_urls': [
            'https://data.oireachtas.ie/ie/oireachtas/members/constituencyBoundaries/2024/',
        ],
    },
    'NZ': {
        'name': 'New Zealand electorates (72)',
        'type': 'direct',
        'url': 'https://datafinder.stats.govt.nz/layer/113533-electoral-boundary-2023/data/geojson',
        'id_col': 'ENAME',
        'name_col': 'ENAME',
        'table': 'church_election_NZ',
        'geo_unit': 'electorate',
        'description': 'NZ general electorate (2023) per church',
    },
    'JP': {
        'name': 'Japan HR districts (289)',
        'type': 'direct',
        'url': 'https://raw.githubusercontent.com/nishad2d8/jp-elections/main/data/hr_districts.geojson',
        'id_col': 'district',
        'name_col': 'district',
        'table': 'church_election_JP',
        'geo_unit': 'district',
        'description': 'House of Representatives district per church',
        'skip': True,
        'note': 'GitHub repo may not exist; fallback to ADM1',
    },
    'KR': {
        'name': 'South Korea Assembly districts (254)',
        'type': 'direct',
        'url': 'https://raw.githubusercontent.com/southkorea/elections/master/data/districts-2024.geojson',
        'id_col': 'district',
        'name_col': 'district',
        'table': 'church_election_KR',
        'geo_unit': 'district',
        'description': 'National Assembly constituency per church',
        'skip': True,
        'note': 'GitHub repo may not exist; fallback to ADM1',
    },
    'FR': {
        'name': 'France legislative circonscriptions (577)',
        'type': 'direct',
        'url': 'https://www.data.gouv.fr/fr/datasets/r/contours-des-circonscriptions-legislatives-2024/',
        'id_col': 'code',
        'name_col': 'nom',
        'table': 'church_election_FR',
        'geo_unit': 'circonscription',
        'description': 'Assemblée Nationale circonscription (2024) per church',
        'fallback_urls': [
            'https://static.data.gouv.fr/resources/contours-des-circonscriptions-legislatives-2024/20240610-140000/circonscriptions-legislatives-2024.geojson',
        ],
        'note': '577 circonscriptions — replaces departement-level church_election_FR',
    },
    'IT': {
        'name': 'Italy Camera constituencies (147)',
        'type': 'direct',
        'url': 'https://www.istat.it/storage/cartografia/confini_amministrativi/collegi/Coll_uninom_Camera_2020_WGS84.zip',
        'id_col': 'CU20_COD',
        'name_col': 'CU20_DEN',
        'table': 'church_election_IT',
        'geo_unit': 'collegio',
        'description': 'Camera dei Deputati uninominal college per church',
        'skip': True,
        'note': 'ZIP file — needs special handling; fallback to ADM1',
    },
}

# ── ArcGIS Downloader ────────────────────────────────────────────────

def download_arcgis(info):
    """Download all features from an ArcGIS FeatureServer as GeoJSON."""
    dest = DATA_DIR / info['file'] if 'file' in info else DATA_DIR / f'{info["table"].replace("church_election_","")}_electoral.geojson'
    
    if dest.exists() and dest.stat().st_size > 1000:
        print(f'    Already downloaded: {dest.name}')
        return dest
    
    base_url = info['url']
    print(f'    Querying ArcGIS FeatureServer...')
    
    # First, get count
    try:
        count_url = f'{base_url}/query?where=1%3D1&returnCountOnly=true&f=json'
        req = urllib.request.Request(count_url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
            count_data = json.loads(r.read())
        total = count_data.get('count', 0)
        print(f'    {total} features total')
    except Exception as e:
        print(f'    Failed to get count: {e}')
        total = '?'
    
    # Download in pages (ArcGIS max 1000 per request, but most electoral datasets are <1000)
    all_features = []
    offset = 0
    page_size = 1000
    
    while True:
        query_url = f'{base_url}/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson&resultOffset={offset}&resultRecordCount={page_size}'
        
        try:
            req = urllib.request.Request(query_url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as r:
                data = json.loads(r.read())
            
            features = data.get('features', [])
            if not features:
                break
            
            all_features.extend(features)
            print(f'    Downloaded {len(all_features)}/{total}...', end='\r')
            
            if len(features) < page_size:
                break
            offset += page_size
            
        except Exception as e:
            print(f'\n    Error at offset {offset}: {e}')
            break
    
    if not all_features:
        print(f'\n    No features downloaded')
        return None
    
    # Build GeoJSON
    geojson = {
        'type': 'FeatureCollection',
        'features': all_features
    }
    
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(geojson, f)
    
    size_mb = dest.stat().st_size / (1024*1024)
    print(f'\n    Saved {len(all_features)} features, {size_mb:.1f} MB → {dest.name}')
    return dest


def download_direct(info):
    """Download a file directly from URL."""
    dest = DATA_DIR / info['file'] if 'file' in info else DATA_DIR / f'{info["table"].replace("church_election_","")}_electoral.geojson'
    
    if dest.exists() and dest.stat().st_size > 1000:
        print(f'    Already downloaded: {dest.name}')
        return dest
    
    urls = [info['url']] + info.get('fallback_urls', [])
    
    for url in urls:
        print(f'    Trying: {url[:80]}...')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 GRID/1.0'})
            with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as r:
                data = r.read()
            
            # Try parsing as GeoJSON
            content = json.loads(data)
            with open(dest, 'w', encoding='utf-8') as f:
                json.dump(content, f)
            
            size_mb = len(data) / (1024*1024)
            print(f'    Downloaded {size_mb:.1f} MB → {dest.name}')
            return dest
        except Exception as e:
            print(f'    Failed: {e}')
            continue
    
    return None

# ── Spatial Join ─────────────────────────────────────────────────────

def spatial_join_and_store(db, info, gdf, iso):
    """Spatial join churches → electoral districts, replace existing table."""
    table = info['table']
    id_col = info['id_col']
    name_col = info['name_col']
    
    # Find actual columns in GeoDataFrame
    actual_id = id_col if id_col in gdf.columns else None
    actual_name = name_col if name_col in gdf.columns else None
    
    if actual_id is None:
        # Try to find suitable ID column
        for col in gdf.columns:
            low = col.lower()
            if 'nr' in low or 'id' in low or 'code' in low or 'number' in low:
                actual_id = col
                break
        if actual_id is None:
            actual_id = gdf.columns[0]
    
    if actual_name is None:
        for col in gdf.columns:
            low = col.lower()
            if 'name' in low:
                actual_name = col
                break
        if actual_name is None:
            actual_name = actual_id
    
    print(f'    ID={actual_id}, Name={actual_name}')
    
    # Load churches with GPS
    c = db.cursor()
    c.execute(f"""
        SELECT rowid, latitude, longitude 
        FROM churches 
        WHERE country='{iso}' AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    churches = c.fetchall()
    print(f'    {len(churches):,} churches with GPS')
    
    if not churches:
        return 0
    
    # Build GeoDataFrames
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': [r[0] for r in churches]},
        geometry=[Point(r[2], r[1]) for r in churches],
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != gdf.crs:
        church_gdf = church_gdf.to_crs(gdf.crs)
    
    # Ensure only needed columns
    gdf_clean = gdf[[actual_id, actual_name, 'geometry']].copy()
    
    # Spatial join
    print(f'    Spatial join...', end=' ', flush=True)
    joined = gpd.sjoin(church_gdf, gdf_clean, how='left', predicate='within')
    matched = joined[actual_id].notna().sum()
    print(f'{matched:,}/{len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    # Drop old table, create new
    c.execute(f'DROP TABLE IF EXISTS {table}')
    
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
    
    # Batch insert
    result = joined[['church_rowid', actual_id, actual_name]].dropna(subset=[actual_id])
    rows = [(int(r.church_rowid), str(getattr(r, actual_id)), str(getattr(r, actual_name)))
            for r in result.itertuples()]
    
    for i in range(0, len(rows), CHUNK):
        chunk = rows[i:i+CHUNK]
        db.executemany(
            f'INSERT INTO {table} (church_rowid, dist_code, dist_name, source) VALUES (?,?,?,?)',
            [(r[0], r[1], r[2], info['name']) for r in chunk]
        )
    
    db.commit()
    print(f'    Wrote {len(rows):,} rows to {table}')
    
    # Update catalog
    c.execute('''INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, row_count, source_date)
        VALUES (?,?,?,?,?,?,date('now'))''',
        (iso, table, 'election', info['geo_unit'], info['description'], len(rows)))
    
    return len(rows)


def log(msg):
    print(f'  [{datetime.now().strftime("%H:%M:%S")}] {msg}')


# ── Main ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    db = sqlite3.connect(str(DB))
    db.execute('PRAGMA journal_mode=WAL')
    
    print('=' * 60)
    print(f'  ELECTORAL BOUNDARY IMPORT v2 — {len(SOURCES)} countries')
    print('  Sources: ArcGIS FeatureServers + direct downloads')
    print('=' * 60)
    
    success = 0; failed = 0; skipped = 0
    
    for iso, info in SOURCES.items():
        print(f'\n{"─"*60}')
        print(f'  {iso} — {info["name"]}')
        print(f'{"─"*60}')
        
        if info.get('skip'):
            print(f'    ⏭ SKIPPING: {info.get("note", "")}')
            skipped += 1
            continue
        
        # Download
        if info['type'] == 'arcgis':
            fname = download_arcgis(info)
        else:
            fname = download_direct(info)
        
        if not fname:
            print(f'    ❌ FAILED to download')
            failed += 1
            continue
        
        # Load and spatial join
        try:
            gdf = gpd.read_file(fname)
            print(f'    {len(gdf):,} features, CRS: {gdf.crs}, cols: {list(gdf.columns)[:6]}')
            
            n = spatial_join_and_store(db, info, gdf, iso)
            log(f'  ✓ {info["name"]}: {n:,} churches')
            success += 1
        except Exception as e:
            print(f'    ❌ FAILED: {e}')
            import traceback
            traceback.print_exc()
            failed += 1
    
    elapsed = time.time() - t0
    print(f'\n{"="*60}')
    print(f'  {success} succeeded, {failed} failed, {skipped} skipped — {elapsed/60:.1f} min')
    db.close()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Download actual electoral district shapefiles and spatial join churches→districts.
Replaces ADM1-based church_election tables with real electoral boundaries.

Priority countries (have election results needing matching):
  IE — 43 Dáil constituencies (currently 4 ADM1 provinces → 0 matches)
  NZ — 72 electorates (currently 18 ADM1 regions → 6/71 matched)
  KR — 254 National Assembly districts (currently 17 ADM1 provinces)
  JP — 289 HR single-seat districts (currently 47 ADM1 prefectures)
  DE — 299 Bundestag wahlkreise (empty table)
  IT — Chamber/ Senate collegi (empty table)
  SE — 29 Riksdag constituencies (currently 21 ADM1 län)
  NO — 19 Storting constituencies (currently 11 ADM1 fylker)
  NL — 20 electoral districts (currently 12 ADM1 provinces)
  TW — 73 legislative districts (currently 22 ADM1 counties)

Data sources:
  - geoBoundaries ADM1 (fallback for most)
  - OSM / government open data portals
  - Wikipedia-derived boundary files
"""

import io, json, os, re, sqlite3, ssl, sys, tempfile, time, urllib.request, zipfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DB = Path(r'E:\grid\churches.db')
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


# ── Country Configs ─────────────────────────────────────────────────

SOURCES = {
    'DE': {
        'name': 'Germany Bundestag wahlkreise (299)',
        'url': 'https://www.bundeswahlleiterin.de/bundestagswahlen/2025/wahlkreiseinteilung/downloads/btw25_wahlkreise_geo_shp.zip',
        'file': 'btw25_wahlkreise_geo_shp.zip',
        'format': 'zip_shp',
        'id_col': 'WKR_NR',
        'name_col': 'WKR_NAME',
        'table': 'church_election_DE',
        'geo_unit': 'wahlkreis',
        'description': 'Bundestag constituency 2025 per church',
    },
    'IE': {
        'name': 'Ireland Dáil constituencies (43)',
        'url': 'https://raw.githubusercontent.com/rdmolony/dail-constituencies/master/dail-constituencies.geojson',
        'file': 'ie_dail_constituencies.geojson',
        'format': 'geojson',
        'id_col': 'name',
        'name_col': 'name',
        'table': 'church_election_IE',
        'geo_unit': 'constituency',
        'description': 'Dáil Éireann constituency (2024 boundaries) per church',
    },
    'NZ': {
        'name': 'New Zealand general electorates (72)',
        'url': 'https://github.com/nz-election-studies/nzes2023/raw/main/data/electorate_boundaries_2023.geojson',
        'file': 'nz_electorates_2023.geojson',
        'format': 'geojson',
        'id_col': 'electorate',
        'name_col': 'electorate',
        'table': 'church_election_NZ',
        'geo_unit': 'electorate',
        'description': 'NZ general electorate (2023 boundaries) per church',
        'fallback_url': 'https://datafinder.stats.govt.nz/layer/113533-electoral-boundary-2023/',
        'fallback_note': 'Stats NZ Data Service may require API key',
    },
    'KR': {
        'name': 'South Korea National Assembly districts (254)',
        'url': 'https://raw.githubusercontent.com/southkorea/elections/master/data/districts-2024.geojson',
        'file': 'kr_assembly_districts.geojson',
        'format': 'geojson',
        'id_col': 'district',
        'name_col': 'district',
        'table': 'church_election_KR',
        'geo_unit': 'constituency',
        'description': 'National Assembly constituency (2024) per church',
    },
    'JP': {
        'name': 'Japan HR single-seat districts (289)',
        'url': 'https://raw.githubusercontent.com/nishad2d8/jp-elections/main/data/hr_districts.geojson',
        'file': 'jp_hr_districts.geojson',
        'format': 'geojson',
        'id_col': 'district',
        'name_col': 'district',
        'table': 'church_election_JP',
        'geo_unit': 'district',
        'description': 'House of Representatives single-seat district per church',
    },
    'IT': {
        'name': 'Italy Chamber collegi uninominali (147)',
        'url': None,  # Need to source — Istat or Ministero dell'Interno
        'file': 'it_collegi.geojson',
        'format': 'geojson',
        'id_col': 'collegio',
        'name_col': 'collegio',
        'table': 'church_election_IT',
        'geo_unit': 'collegio',
        'description': 'Camera dei Deputati uninominal college per church',
        'skip': True,
        'note': 'Shapefile not yet sourced — needs Istat/openpolis data',
    },
    'SE': {
        'name': 'Sweden Riksdag constituencies (29)',
        'url': 'https://github.com/swedish-opendata/valgeografi/raw/main/data/riksdagsvalkretsar.geojson',
        'file': 'se_riksdag_constituencies.geojson',
        'format': 'geojson',
        'id_col': 'valkrets',
        'name_col': 'valkrets',
        'table': 'church_election_SE',
        'geo_unit': 'valkrets',
        'description': 'Riksdag constituency per church',
    },
    'NO': {
        'name': 'Norway Storting constituencies (19)',
        'url': 'https://github.com/norwegian-elections/valgdata/raw/main/geometries/valgdistrikt_2025.geojson',
        'file': 'no_valgdistrikt.geojson',
        'format': 'geojson',
        'id_col': 'valgdistrikt',
        'name_col': 'valgdistrikt',
        'table': 'church_election_NO',
        'geo_unit': 'valgdistrikt',
        'description': 'Storting electoral district per church',
    },
    'NL': {
        'name': 'Netherlands electoral districts (20)',
        'url': 'https://github.com/openstate/nl-electoral-districts/raw/main/data/kieskringen.geojson',
        'file': 'nl_kieskringen.geojson',
        'format': 'geojson',
        'id_col': 'kieskring',
        'name_col': 'kieskring',
        'table': 'church_election_NL',
        'geo_unit': 'kieskring',
        'description': 'Tweede Kamer electoral district per church',
    },
    'TW': {
        'name': 'Taiwan legislative districts (73)',
        'url': None,  # Taiwan open data portal
        'file': 'tw_legislative_districts.geojson',
        'format': 'geojson',
        'id_col': 'district',
        'name_col': 'district',
        'table': 'church_election_TW',
        'geo_unit': 'district',
        'description': 'Legislative Yuan constituency per church',
        'skip': True,
        'note': 'Taiwan open data shapefiles needed — use geoBoundaries ADM1 for now',
    },
}

# ── Helpers ──────────────────────────────────────────────────────────

def log(msg):
    print(f'  [{datetime.now().strftime("%H:%M:%S")}] {msg}')

def download_file(info):
    """Download boundary file, return path."""
    dest = DATA_DIR / info['file']
    if dest.exists() and dest.stat().st_size > 1000:
        print(f'    Already downloaded: {info["file"]}')
        return dest
    
    url = info.get('url')
    if not url:
        print(f'    No download URL — SKIPPING: {info.get("note","")}')
        return None
    
    print(f'    Downloading {info["name"]}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 GRID/1.0'})
        with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as resp:
            data = resp.read()
        with open(dest, 'wb') as f:
            f.write(data)
        size_mb = len(data) / (1024*1024)
        print(f'{size_mb:.1f} MB')
        return dest
    except Exception as e:
        print(f'FAILED: {e}')
        # Try fallback
        fallback = info.get('fallback_url')
        if fallback:
            print(f'    Trying fallback...')
            try:
                req = urllib.request.Request(fallback, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as resp:
                    data = resp.read()
                with open(dest, 'wb') as f:
                    f.write(data)
                print(f'    Downloaded via fallback: {len(data)/1024/1024:.1f} MB')
                return dest
            except:
                pass
        return None

def load_boundaries(info):
    """Load boundary GeoDataFrame from downloaded file."""
    fname = DATA_DIR / info['file']
    if not fname.exists():
        return None
    
    fmt = info['format']
    if fmt == 'zip_shp':
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(fname, 'r') as zf:
                zf.extractall(tmp)
            shp_files = list(Path(tmp).glob('**/*.shp'))
            if not shp_files:
                print(f'    No .shp found in archive')
                return None
            gdf = gpd.read_file(shp_files[0])
    elif fmt == 'geojson':
        gdf = gpd.read_file(fname)
    else:
        print(f'    Unknown format: {fmt}')
        return None
    
    print(f'    {len(gdf):,} features, CRS: {gdf.crs}')
    return gdf

def spatial_join_and_store(db, info, gdf, iso):
    """Spatial join churches → electoral districts, replace existing table."""
    table = info['table']
    id_col = info['id_col']
    name_col = info['name_col']
    
    # Find actual columns
    actual_id = id_col if id_col in gdf.columns else next(
        (c for c in gdf.columns if 'id' in c.lower() or 'code' in c.lower() or 
         'nr' in c.lower() or 'name' in c.lower()), gdf.columns[0])
    actual_name = name_col if name_col in gdf.columns else actual_id
    
    print(f'    Using ID={actual_id}, Name={actual_name}')
    
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
    
    # Spatial join
    print(f'    Spatial join...', end=' ', flush=True)
    joined = gpd.sjoin(church_gdf, gdf[[actual_id, actual_name, 'geometry']],
                       how='left', predicate='within')
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


# ── Main ─────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    db = sqlite3.connect(str(DB))
    db.execute('PRAGMA journal_mode=WAL')
    
    # Filter: skip already-done countries that have actual boundaries
    # GB and AU already have constituency boundaries from _enrich_batch.py
    # FR already has circonscriptions
    # IN already has Lok Sabha constituencies
    
    print('=' * 60)
    print(f'  ELECTORAL BOUNDARY IMPORT — {len(SOURCES)} countries')
    print('=' * 60)
    
    success = 0
    skipped = 0
    failed = 0
    
    for iso, info in SOURCES.items():
        print(f'\n{"─"*60}')
        print(f'  {iso} — {info["name"]}')
        print(f'{"─"*60}')
        
        if info.get('skip'):
            print(f'    ⏭ SKIPPING: {info.get("note","")}')
            skipped += 1
            continue
        
        # Download
        fname = download_file(info)
        if not fname:
            print(f'    FAILED to download')
            failed += 1
            continue
        
        # Load boundaries
        try:
            gdf = load_boundaries(info)
        except Exception as e:
            print(f'    FAILED to load: {e}')
            failed += 1
            continue
        
        if gdf is None:
            print(f'    FAILED — no data')
            failed += 1
            continue
        
        # Spatial join
        try:
            n = spatial_join_and_store(db, info, gdf, iso)
            log(f'  ✓ {info["name"]}: {n:,} churches')
            success += 1
        except Exception as e:
            print(f'    FAILED: {e}')
            import traceback
            traceback.print_exc()
            failed += 1
    
    elapsed = time.time() - t0
    print(f'\n{"="*60}')
    print(f'  {success} succeeded, {failed} failed, {skipped} skipped — {elapsed/60:.1f} min')
    db.close()

if __name__ == '__main__':
    main()

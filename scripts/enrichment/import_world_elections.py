"""
Import election data for countries missing electoral district coverage.

Creates: church_election_{ISO2} bridge tables + election_{country}_results tables

Countries (in priority order):
  1. IN — India (225K churches) → Lok Sabha 543 constituencies
  2. DE — Germany (105K) → Bundestag 299 wahlkreise (boundary script exists)  
  3. JP — Japan (158K) → HR 289 single-seat districts
  4. ID — Indonesia (151K) → DPR 84 electoral districts
  ... more to follow

Usage:
    python scripts/enrichment/import_world_elections.py                        # all countries
    python scripts/enrichment/import_world_elections.py --country IN           # India only
    python scripts/enrichment/import_world_elections.py --country IN,DE        # specific countries
    python scripts/enrichment/import_world_elections.py --dry-run              # preview only

Data sources:
  - Boundaries: geoBoundaries / country-specific open data portals / GitHub
  - Results: Wikipedia tables / government election commission APIs
"""

import sqlite3, io, json, os, re, sys, ssl, time, urllib.request, zipfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = Path(r'E:\grid\data\election_results')
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

# SSL workaround for government sites
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


# ── Country Configs ──────────────────────────────────────────────────

COUNTRIES = {
    'IN': {
        'iso': 'IN',
        'name': 'India',
        'churches': 225880,
        'boundary_url': 'https://raw.githubusercontent.com/datameet/maps/master/parliamentary-constituencies/india_pc_2019_simplified.geojson',
        'boundary_file': 'india_pc_2019_simplified.geojson',
        'id_col': 'pc_id',
        'name_col': 'pc_name',
        'table': 'church_election_IN',
        'geo_unit': 'constituency',
        'description': 'Lok Sabha parliamentary constituency per church (2019 boundaries)',
        'results_source': 'wikipedia',
        'results_url': 'https://en.wikipedia.org/wiki/2024_Indian_general_election',
        'results_table': 'election_india_ls_results',
    },
    'DE': {
        'iso': 'DE',
        'name': 'Germany',
        'churches': 105431,
        'boundary_url': 'https://www.bundeswahlleiterin.de/bundestagswahlen/2025/wahlkreiseinteilung/downloads/btw25_wahlkreise_geo_shp.zip',
        'boundary_file': 'btw25_wahlkreise_geo_shp.zip',
        'format': 'zip_shp',
        'id_col': 'WKR_NR',
        'name_col': 'WKR_NAME',
        'table': 'church_election_DE',
        'geo_unit': 'wahlkreis',
        'description': 'Bundestag constituency 2025 per church',
        'results_source': 'wikipedia',
        'results_url': 'https://en.wikipedia.org/wiki/2025_German_federal_election',
        'results_table': 'election_germany_bt_results',
    },
    'JP': {
        'iso': 'JP',
        'name': 'Japan',
        'churches': 158023,
        # Japan HR single-seat district boundaries from MLIT
        # Using geoBoundaries ADM1 as fallback (HR districts are sub-prefecture level)
        'boundary_url': None,  # Needs MLIT download — use census ADM1 as approximation
        'boundary_file': None,
        'skip_boundary': True,
        'note': 'JP HR district boundaries not yet sourced — needs MLIT shapefile',
    },
    'ID': {
        'iso': 'ID',
        'name': 'Indonesia',
        'churches': 151538,
        # Indonesia DPR electoral districts (dapil)
        'boundary_url': None,  # KPU shapefiles needed
        'boundary_file': None,
        'skip_boundary': True,
        'note': 'Indonesia dapil boundaries not yet sourced — needs KPU shapefile',
    },
}


def download_file(url, dest, label):
    """Download a file with progress."""
    if dest.exists():
        print(f'  Already downloaded: {dest.name}')
        return True
    
    print(f'  Downloading {label}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=300, context=ssl_ctx) as resp:
            with open(dest, 'wb') as f:
                f.write(resp.read())
        size_mb = os.path.getsize(dest) / (1024*1024)
        print(f'{size_mb:.1f} MB')
        return True
    except Exception as e:
        print(f'FAILED: {e}')
        return False


def load_geodata(cfg):
    """Load electoral boundary GeoDataFrame from file or URL."""
    fname = cfg.get('boundary_file')
    if not fname:
        return None
    
    dest = DATA_DIR / fname
    fmt = cfg.get('format', 'geojson')
    
    # Download if needed
    url = cfg.get('boundary_url')
    if url and not dest.exists():
        if not download_file(url, dest, cfg['name']):
            return None
    
    if not dest.exists():
        print(f'  No boundary file: {dest}')
        return None
    
    # Handle zip files
    if fmt == 'zip_shp':
        import tempfile, shutil
        tmpdir = Path(tempfile.mkdtemp())
        try:
            with zipfile.ZipFile(dest, 'r') as zf:
                zf.extractall(tmpdir)
            shp_files = list(tmpdir.glob('*.shp'))
            if not shp_files:
                print(f'  No .shp found in {fname}')
                return None
            gdf = gpd.read_file(shp_files[0])
            print(f'  Loaded {len(gdf):,} electoral districts from {fname}')
            return gdf
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
    elif fmt == 'geojson':
        gdf = gpd.read_file(dest)
        print(f'  Loaded {len(gdf):,} electoral districts from {fname}')
        return gdf
    
    return None


def spatial_join_churches(db, gdf, cfg):
    """Spatial join churches to electoral districts."""
    iso = cfg['iso']
    table = cfg['table']
    id_col = cfg['id_col']
    name_col = cfg['name_col']
    
    # Check if id_col exists in GeoDataFrame
    if id_col not in gdf.columns:
        print(f'  WARNING: id_col "{id_col}" not found. Available: {list(gdf.columns)[:10]}...')
        # Try to find a suitable ID column
        for col in gdf.columns:
            if 'code' in col.lower() or 'id' in col.lower() or 'nr' in col.lower():
                id_col = col
                print(f'  Using {id_col} as ID column')
                break
    
    if name_col not in gdf.columns:
        print(f'  WARNING: name_col "{name_col}" not found. Available: {list(gdf.columns)[:10]}...')
        for col in gdf.columns:
            if 'name' in col.lower():
                name_col = col
                print(f'  Using {name_col} as name column')
                break
    
    # Load churches with GPS
    print(f'  Loading {iso} churches with GPS...', end=' ', flush=True)
    c = db.cursor()
    c.execute(f"""
        SELECT rowid, id, name, latitude, longitude, city, state
        FROM churches 
        WHERE country = '{iso}' 
        AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    church_rows = c.fetchall()
    print(f'{len(church_rows):,}')
    
    if not church_rows:
        print('  No churches with GPS!')
        return 0
    
    # Build GeoDataFrame of churches
    church_geoms = [Point(lon, lat) for _, _, _, lat, lon, _, _ in church_rows]
    church_gdf = gpd.GeoDataFrame(
        [(r[0], r[1], r[2], r[5], r[6]) for r in church_rows],
        columns=['rowid', 'id', 'name', 'city', 'state'],
        geometry=church_geoms,
        crs='EPSG:4326'
    )
    
    # Ensure boundary CRS matches
    if gdf.crs is None:
        gdf = gdf.set_crs('EPSG:4326')
    elif gdf.crs != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')
    
    # Spatial join
    print(f'  Spatial join ({len(church_gdf):,} churches x {len(gdf):,} districts)...', end=' ', flush=True)
    t0 = time.time()
    joined = gpd.sjoin(church_gdf, gdf[['geometry', id_col, name_col]], how='inner', predicate='within')
    elapsed = time.time() - t0
    print(f'{len(joined):,} matched in {elapsed:.1f}s')
    
    # Create table
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
    rows_to_insert = []
    for _, row in joined.iterrows():
        dist_code = str(row[id_col]) if pd.notna(row[id_col]) else ''
        dist_name = str(row[name_col]) if pd.notna(row[name_col]) else ''
        rows_to_insert.append((int(row['rowid']), dist_code, dist_name, 
                               cfg.get('description', ''), source_date))
    
    for i in range(0, len(rows_to_insert), CHUNK):
        chunk = rows_to_insert[i:i+CHUNK]
        c.executemany(f'INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?)', chunk)
    
    db.commit()
    
    # Update catalog
    try:
        c.execute("""
            INSERT OR REPLACE INTO church_census_catalog 
            (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
            VALUES (?, ?, 'election', ?, ?, 3, ?, ?, ?)
        """, (iso, table, cfg['geo_unit'], cfg['description'], len(rows_to_insert), source_date, now))
        db.commit()
    except Exception as e:
        print(f'  Catalog update failed (non-fatal): {e}')
    
    print(f'  Created {table}: {len(rows_to_insert):,} rows')
    return len(rows_to_insert)


def scrape_wikipedia_election_results(cfg):
    """Scrape election results from Wikipedia."""
    url = cfg.get('results_url')
    if not url or cfg.get('results_source') != 'wikipedia':
        return None, None
    
    country = cfg['name']
    print(f'  Fetching {country} election results from Wikipedia...', end=' ', flush=True)
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (research)'})
        with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
            html = resp.read().decode('utf-8')
    except Exception as e:
        print(f'FAILED: {e}')
        return None, None
    
    # Parse tables with pandas
    try:
        tables = pd.read_html(io.StringIO(html))
        print(f'{len(tables)} tables found')
    except Exception as e:
        print(f'No tables parsed: {e}')
        return None, None
    
    return tables, html


def import_india_election_results(db, cfg):
    """Import India 2024 Lok Sabha election results from Wikipedia."""
    print('\n--- India 2024 Lok Sabha Results ---')
    
    tables, html = scrape_wikipedia_election_results(cfg)
    if tables is None:
        print('  Could not fetch Wikipedia data')
        return
    
    # The 2024 Indian general election page has results by constituency
    # Try to find the right table(s)
    results = []
    
    for i, table in enumerate(tables):
        # Look for tables with constituency-level data
        cols = [str(c).lower() for c in table.columns]
        has_constituency = any('constituen' in c for c in cols)
        has_party = any('party' in c for c in cols) or any('alliance' in c for c in cols)
        has_candidate = any('candidate' in c for c in cols)
        
        if has_constituency and (has_party or has_candidate):
            print(f'  Table {i}: {len(table)} rows, cols={list(table.columns)[:8]}')
            
            # Try to extract: constituency, winner, party, margin, etc.
            for _, row in table.iterrows():
                try:
                    record = {}
                    for c in table.columns:
                        cl = str(c).lower()
                        val = str(row[c]) if pd.notna(row[c]) else ''
                        if 'constituen' in cl:
                            record['constituency'] = val.strip()
                        elif 'state' in cl and 'state' not in record:
                            record['state'] = val.strip()
                        elif 'candidate' in cl or 'winner' in cl or 'elected' in cl:
                            record['winner'] = val.strip()
                        elif 'party' in cl and 'party' not in record:
                            record['winner_party'] = val.strip()
                        elif 'alliance' in cl:
                            record['alliance'] = val.strip()
                        elif 'margin' in cl:
                            record['margin'] = val.strip()
                        elif 'turnout' in cl:
                            record['turnout'] = val.strip()
                        elif 'elector' in cl or 'voter' in cl:
                            record['electorate'] = val.strip()
                    
                    if record.get('constituency') and record.get('winner'):
                        results.append(record)
                except:
                    pass
    
    # If structured parsing didn't work well, try a simpler approach
    if len(results) < 100:
        print(f'  Structured parse only got {len(results)} results. Trying broader approach...')
        results = []
        for table in tables:
            if len(table.columns) >= 3 and len(table) > 50:
                # Try to map columns heuristically
                cols = [str(c) for c in table.columns]
                for _, row in table.iterrows():
                    vals = [str(v) if pd.notna(v) else '' for v in row.values]
                    # Look for rows that look like constituency results
                    if len(vals) >= 3 and vals[0] and vals[1]:
                        results.append({
                            'constituency': vals[0].strip(),
                            'state': '',
                            'winner': vals[1].strip() if len(vals) > 1 else '',
                            'winner_party': vals[2].strip() if len(vals) > 2 else '',
                            'alliance': '',
                            'margin': '',
                            'turnout': '',
                            'electorate': '',
                        })
    
    print(f'  Parsed {len(results)} constituency results')
    
    if not results:
        print('  No results parsed. Wikipedia table format may have changed.')
        return
    
    # Save to DB
    c = db.cursor()
    now = datetime.now().isoformat()
    table = cfg.get('results_table', 'election_india_ls_results')
    
    c.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            constituency TEXT PRIMARY KEY,
            state TEXT,
            winner TEXT,
            winner_party TEXT,
            alliance TEXT,
            margin TEXT,
            turnout TEXT,
            electorate TEXT,
            election_year INTEGER DEFAULT 2024,
            source TEXT,
            import_date TEXT
        )
    """)
    
    c.execute(f'DELETE FROM {table}')
    
    inserted = 0
    for r in results:
        try:
            c.execute(f"""
                INSERT INTO {table} (constituency, state, winner, winner_party, alliance, margin, turnout, electorate, source, import_date)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                r.get('constituency', ''),
                r.get('state', ''),
                r.get('winner', ''),
                r.get('winner_party', ''),
                r.get('alliance', ''),
                r.get('margin', ''),
                r.get('turnout', ''),
                r.get('electorate', ''),
                'wikipedia_2024',
                now
            ))
            inserted += 1
        except:
            pass
    
    db.commit()
    print(f'  Imported {inserted} results to {table}')
    
    # Update catalog
    c.execute("""
        INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, col_count, church_count, created_date, updated_date)
        VALUES (?, ?, 'election', ?, ?, 8, ?, ?, ?)
    """, ('IN', table, 'constituency', 'India 2024 Lok Sabha general election results', inserted, now[:10], now))
    db.commit()


def main():
    dry_run = '--dry-run' in sys.argv
    
    # Parse --country flag
    target_countries = None
    for i, arg in enumerate(sys.argv):
        if arg == '--country' and i+1 < len(sys.argv):
            target_countries = [c.strip() for c in sys.argv[i+1].split(',')]
    
    if target_countries:
        countries_to_process = {k: v for k, v in COUNTRIES.items() if k in target_countries}
        if not countries_to_process:
            print(f"No countries matched: {target_countries}")
            print(f"Available: {list(COUNTRIES.keys())}")
            return
    else:
        countries_to_process = COUNTRIES
    
    print("=" * 60)
    print("WORLD ELECTION DATA IMPORTER")
    print("=" * 60)
    print(f"Countries: {', '.join(countries_to_process.keys())}")
    
    if dry_run:
        print("\n=== DRY RUN — no changes ===")
        for iso, cfg in countries_to_process.items():
            status = 'SKIP (no boundaries)' if cfg.get('skip_boundary') else 'READY'
            print(f'  {iso} ({cfg["name"]}): {cfg["churches"]:,} churches — {status}')
        return
    
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    for iso, cfg in countries_to_process.items():
        print(f'\n{"="*60}')
        print(f'{iso} — {cfg["name"]} ({cfg["churches"]:,} churches)')
        print(f'{"="*60}')
        
        if cfg.get('skip_boundary'):
            print(f'  SKIPPED: {cfg.get("note", "No boundary data available")}')
            continue
        
        # Step 1: Load boundaries
        gdf = load_geodata(cfg)
        if gdf is None:
            continue
        
        # Step 2: Spatial join
        matched = spatial_join_churches(db, gdf, cfg)
        
        # Step 3: Import results
        if cfg.get('results_source') == 'wikipedia' and cfg.get('results_url'):
            if iso == 'IN':
                import_india_election_results(db, cfg)
            # Add more country-specific result importers as needed
            else:
                print(f'  No result importer for {iso} yet')
    
    db.close()
    print('\nDone.')


if __name__ == '__main__':
    main()

"""
Quick election results: Nigeria bridge + ZA/DK/NO/AT Wikipedia scrapers.
"""
import sqlite3, json, urllib.request, ssl, time, io, re
from datetime import datetime
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\election_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def download_gb_json(iso, iso3, level='ADM1'):
    """Download geoBoundaries GeoJSON — tries cache first."""
    fname = DATA_DIR / f'gb_{iso}_{level}.geojson'
    if fname.exists():
        return fname
    
    # Try world_boundaries cache (different naming)
    alt_name = DATA_DIR.parent / 'world_boundaries' / f'geoBoundaries-{iso3}-{level}.geojson'
    if alt_name.exists() and alt_name.stat().st_size > 1000:
        print(f'  Using cached: {alt_name.name}')
        return alt_name
    
    # Download from API
    url = f'https://www.geoboundaries.org/api/current/gbOpen/{iso3}/{level}/'
    print(f'  Downloading {iso} {level}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            meta = json.loads(r.read())
    except Exception as e:
        print(f'API FAILED: {e}')
        return None
    
    dl = meta.get('gjDownloadURL')
    if not dl:
        print('No download URL')
        return None
    
    try:
        req = urllib.request.Request(dl, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=300, context=ctx) as r:
            with open(fname, 'wb') as f:
                f.write(r.read())
        print(f'{fname.stat().st_size/(1024*1024):.0f}MB')
        return fname
    except Exception as e:
        print(f'Download FAILED: {e}')
        return None

def spatial_join_country(db, iso, gdf_path, table_name, desc):
    """Spatial join churches to boundaries."""
    gdf = gpd.read_file(gdf_path)
    id_col = 'shapeID'; name_col = 'shapeName'
    
    c = db.cursor()
    c.execute(f"SELECT rowid, id, latitude, longitude FROM churches WHERE country='{iso}' AND latitude IS NOT NULL")
    rows = c.fetchall()
    print(f'  {len(rows):,} churches')
    
    church_gdf = gpd.GeoDataFrame(
        [(r[0], r[1]) for r in rows], columns=['rowid','id'],
        geometry=[Point(lon,lat) for _,_,lat,lon in rows], crs='EPSG:4326')
    
    if str(gdf.crs) != 'EPSG:4326':
        gdf = gdf.to_crs('EPSG:4326')
    
    t0 = time.time()
    joined = gpd.sjoin(church_gdf, gdf[[id_col,name_col,'geometry']], how='inner', predicate='within')
    print(f'  {len(joined):,} matched in {time.time()-t0:.1f}s')
    
    now = datetime.now().isoformat()
    c.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (
        church_rowid INTEGER PRIMARY KEY, dist_code TEXT, dist_name TEXT, source TEXT, source_date TEXT)""")
    c.execute(f'DELETE FROM {table_name}')
    
    data = [(int(row['rowid']), str(row[id_col]), str(row[name_col]), desc, now[:10])
            for _, row in joined.iterrows()]
    
    for i in range(0, len(data), CHUNK):
        c.executemany(f'INSERT OR REPLACE INTO {table_name} VALUES (?,?,?,?,?)', data[i:i+CHUNK])
    db.commit()
    
    # Catalog
    c.execute("""INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', 'state', ?, 3, ?, ?, ?)""",
        (iso, table_name, desc, len(data), now[:10], now))
    db.commit()
    return len(data)

def scrape_wikipedia_table(url, table_index=0):
    """Scrape a Wikipedia results table."""
    req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0 (research)'})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        html = r.read().decode('utf-8')
    tables = pd.read_html(io.StringIO(html))
    return tables

def import_election_results(db, table_name, rows, columns, catalog_desc):
    """Batch insert election results."""
    c = db.cursor()
    
    col_defs = ', '.join(f'{col} TEXT' for col in columns)
    c.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs}, source TEXT, import_date TEXT)""")
    c.execute(f'DELETE FROM {table_name}')
    
    now = datetime.now().isoformat()
    placeholders = ', '.join('?' for _ in columns)
    data = []
    for row in rows:
        vals = [str(row.get(c, '')) if row.get(c) is not None else '' for c in columns]
        data.append(tuple(vals + ['wikipedia', now]))
    
    for i in range(0, len(data), CHUNK):
        c.executemany(f'INSERT INTO {table_name} ({", ".join(columns)}, source, import_date) VALUES ({placeholders}, ?, ?)', data[i:i+CHUNK])
    db.commit()
    
    # Catalog
    c.execute("""INSERT OR REPLACE INTO church_census_catalog 
        (country, table_name, category, geo_unit, description, variable_count, row_count, source_date, refresh_date)
        VALUES (?, ?, 'election', ?, ?, ?, ?, ?, ?)""",
        (table_name.split('_')[1] if '_' in table_name else '??', table_name, 'province', 
         catalog_desc, len(columns), len(data), now[:10], now))
    db.commit()
    return len(data)


# ═══════════════════════════════════════════════════════════════
# NIGERIA: spatial join to states
# ═══════════════════════════════════════════════════════════════
print('='*60)
print('NIGERIA — church_election_NG bridge')
print('='*60)

db = sqlite3.connect(DB, timeout=120)
db.execute("PRAGMA journal_mode=WAL")

fname = download_gb_json('NG', 'NGA', 'ADM1')
if fname:
    matched = spatial_join_country(db, 'NG', fname, 'church_election_NG', 
        'geoBoundaries ADM1 — Nigeria state = electoral district')
    total = db.execute('SELECT COUNT(*) FROM churches WHERE country="NG"').fetchone()[0]
    print(f'  -> church_election_NG: {matched:,}/{total:,} ({100*matched/total:.0f}%)')
else:
    print('  SKIPPED — could not download NGA ADM1')
db.close()

# ═══════════════════════════════════════════════════════════════
# SOUTH AFRICA: scrape 2024 general election
# ═══════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('SOUTH AFRICA — 2024 general election results')
print('='*60)

try:
    tables = scrape_wikipedia_table('https://en.wikipedia.org/wiki/2024_South_African_general_election')
    
    # Find the national results table by province
    za_results = []
    for i, t in enumerate(tables):
        cols = [str(c).lower() for c in t.columns]
        # Look for province-level breakdown
        has_province = any('province' in c for c in cols)
        has_anc = any('anc' in str(c).lower() for c in t.iloc[0] if pd.notna(t.iloc[0][c])) if len(t) > 0 else False
        
        if has_province or (len(t.columns) >= 4 and len(t) < 15):
            print(f'  Table {i}: {len(t)} rows, cols={list(t.columns)[:6]}')
            
            for _, row in t.iterrows():
                vals = [str(v) for v in row.values if pd.notna(v)]
                if len(vals) >= 2 and vals[0]:
                    # Check if this looks like a province row
                    province = vals[0].strip()
                    # Skip header rows
                    if province.lower() in ('province', 'party', 'total', ''):
                        continue
                    za_results.append({
                        'province': province,
                        'raw_data': '|'.join(vals)
                    })
    
    print(f'  Parsed {len(za_results)} province results')
    
    if za_results:
        db2 = sqlite3.connect(DB)
        c = db2.cursor()
        now = datetime.now().isoformat()
        c.execute("""CREATE TABLE IF NOT EXISTS election_za_province_results (
            province TEXT PRIMARY KEY, raw_data TEXT, election_year INTEGER DEFAULT 2024, source TEXT, import_date TEXT)""")
        c.execute('DELETE FROM election_za_province_results')
        for r in za_results:
            c.execute('INSERT INTO election_za_province_results VALUES (?,?,2024,?,?)',
                     (r['province'], r['raw_data'], 'wikipedia_2024', now))
        db2.commit()
        db2.close()
        print(f'  Imported {len(za_results)} province results')
except Exception as e:
    print(f'  FAILED: {e}')

# ═══════════════════════════════════════════════════════════════
# DENMARK: scrape 2022 Folketing election
# ═══════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('DENMARK — 2022 Folketing election results')
print('='*60)

try:
    tables = scrape_wikipedia_table('https://en.wikipedia.org/wiki/2022_Danish_general_election')
    
    dk_results = []
    for i, t in enumerate(tables):
        cols = [str(c).lower() for c in t.columns]
        # Look for regional breakdown
        if len(t.columns) >= 3 and len(t) >= 3 and len(t) < 30:
            sample = str(t.iloc[0].values)
            if any(kw in sample.lower() for kw in ['copenhagen', 'zealand', 'jutland', 'region', 'district', 'constituency']):
                print(f'  Table {i}: {len(t)} rows, cols={list(t.columns)[:6]}')
                for _, row in t.iterrows():
                    vals = [str(v) for v in row.values if pd.notna(v)]
                    if len(vals) >= 2 and vals[0] and vals[0].strip():
                        dk_results.append({'region': vals[0].strip(), 'raw_data': '|'.join(vals)})
    
    print(f'  Parsed {len(dk_results)} regional results')
    
    if dk_results:
        db2 = sqlite3.connect(DB)
        c = db2.cursor()
        now = datetime.now().isoformat()
        c.execute("""CREATE TABLE IF NOT EXISTS election_dk_region_results (
            region TEXT PRIMARY KEY, raw_data TEXT, election_year INTEGER DEFAULT 2022, source TEXT, import_date TEXT)""")
        c.execute('DELETE FROM election_dk_region_results')
        for r in dk_results:
            c.execute('INSERT INTO election_dk_region_results VALUES (?,?,2022,?,?)',
                     (r['region'], r['raw_data'], 'wikipedia_2022', now))
        db2.commit()
        db2.close()
        print(f'  Imported {len(dk_results)} results')
except Exception as e:
    print(f'  FAILED: {e}')

# ═══════════════════════════════════════════════════════════════
# NORWAY: scrape 2021 Storting election
# ═══════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('NORWAY — 2021 Storting election results')
print('='*60)

try:
    tables = scrape_wikipedia_table('https://en.wikipedia.org/wiki/2021_Norwegian_parliamentary_election')
    
    no_results = []
    for i, t in enumerate(tables):
        cols = [str(c).lower() for c in t.columns]
        if len(t.columns) >= 3 and len(t) >= 5 and len(t) < 40:
            sample = str(t.iloc[0].values).lower()
            if any(kw in sample for kw in ['oslo', 'akershus', 'hordaland', 'county', 'constituency', 'valgdistrikt']):
                print(f'  Table {i}: {len(t)} rows, cols={list(t.columns)[:6]}')
                for _, row in t.iterrows():
                    vals = [str(v) for v in row.values if pd.notna(v)]
                    if len(vals) >= 2 and vals[0] and vals[0].strip():
                        no_results.append({'county': vals[0].strip(), 'raw_data': '|'.join(vals)})
    
    print(f'  Parsed {len(no_results)} county results')
    
    if no_results:
        db2 = sqlite3.connect(DB)
        c = db2.cursor()
        now = datetime.now().isoformat()
        c.execute("""CREATE TABLE IF NOT EXISTS election_no_county_results (
            county TEXT PRIMARY KEY, raw_data TEXT, election_year INTEGER DEFAULT 2021, source TEXT, import_date TEXT)""")
        c.execute('DELETE FROM election_no_county_results')
        for r in no_results:
            c.execute('INSERT INTO election_no_county_results VALUES (?,?,2021,?,?)',
                     (r['county'], r['raw_data'], 'wikipedia_2021', now))
        db2.commit()
        db2.close()
        print(f'  Imported {len(no_results)} results')
except Exception as e:
    print(f'  FAILED: {e}')

# ═══════════════════════════════════════════════════════════════
# AUSTRIA: scrape 2024 National Council election
# ═══════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('AUSTRIA — 2024 National Council election results')
print('='*60)

try:
    tables = scrape_wikipedia_table('https://en.wikipedia.org/wiki/2024_Austrian_legislative_election')
    
    at_results = []
    for i, t in enumerate(tables):
        cols = [str(c).lower() for c in t.columns]
        if len(t.columns) >= 3 and len(t) >= 5 and len(t) < 25:
            sample = str(t.iloc[0].values).lower()
            if any(kw in sample for kw in ['burgenland', 'carinthia', 'styria', 'state', 'land', 'bundesland']):
                print(f'  Table {i}: {len(t)} rows, cols={list(t.columns)[:6]}')
                for _, row in t.iterrows():
                    vals = [str(v) for v in row.values if pd.notna(v)]
                    if len(vals) >= 2 and vals[0] and vals[0].strip():
                        at_results.append({'state': vals[0].strip(), 'raw_data': '|'.join(vals)})
    
    print(f'  Parsed {len(at_results)} state results')
    
    if at_results:
        db2 = sqlite3.connect(DB)
        c = db2.cursor()
        now = datetime.now().isoformat()
        c.execute("""CREATE TABLE IF NOT EXISTS election_at_state_results (
            state TEXT PRIMARY KEY, raw_data TEXT, election_year INTEGER DEFAULT 2024, source TEXT, import_date TEXT)""")
        c.execute('DELETE FROM election_at_state_results')
        for r in at_results:
            c.execute('INSERT INTO election_at_state_results VALUES (?,?,2024,?,?)',
                     (r['state'], r['raw_data'], 'wikipedia_2024', now))
        db2.commit()
        db2.close()
        print(f'  Imported {len(at_results)} results')
except Exception as e:
    print(f'  FAILED: {e}')

# Provenance
db3 = sqlite3.connect(DB)
now = datetime.now().isoformat()
db3.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at,
    churches_updated, fields_populated, records_attempted, status)
    VALUES ('quick_election_results', 'import_election_results.py', ?, ?, 5, 'election_results', 5, 'completed')""",
    (now, now))
db3.commit()
db3.close()

print('\nDone.')

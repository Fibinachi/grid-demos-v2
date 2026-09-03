"""GeoNames postal code enrichment — nearest-neighbor spatial match.

Downloads country-level postal code data from GeoNames and matches
churches to the nearest postal code point within a distance threshold.
Populates zip, city, state from the authoritative postal code data.

Target countries: DE, GB, FR, JP, BR, IT, ES, NL, MX, PL, AU, BE, CH, AT, CZ
"""
import sqlite3
import urllib.request
import ssl
import time
import os
import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from datetime import datetime

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\geonames_postal')
DATA_DIR.mkdir(parents=True, exist_ok=True)
CHUNK = 500

# Distance threshold in km for matching a church to a postal code point
MAX_DIST_KM = 5.0  # ~3 miles — generous enough for rural areas

# Countries to process (ISO2 code, priority)
# Only include countries NOT already processed in the partial run
TARGETS = [
    ('PT', 'Portugal', 17271),
    ('SE', 'Sweden', 11098),
    ('DK', 'Denmark', 6649),
    ('NO', 'Norway', 5775),
    ('FI', 'Finland', 4576),
    ('NZ', 'New Zealand', 6807),
    ('IE', 'Ireland', 6388),
    ('HU', 'Hungary', 11643),
    ('RO', 'Romania', 10367),
    ('GR', 'Greece', 19461),
    ('TR', 'Turkey', 42984),
    ('KR', 'South Korea', 22026),
    ('ZA', 'South Africa', 14264),
    ('AR', 'Argentina', 17848),
    ('CL', 'Chile', 10377),
    ('CO', 'Colombia', 17220),
    ('PE', 'Peru', 10599),
    ('IN', 'India', 225128),
    ('ID', 'Indonesia', 148672),
    ('TH', 'Thailand', 65878),
    ('MY', 'Malaysia', 26707),
    ('PH', 'Philippines', 55193),
    ('RU', 'Russia', 31599),
    ('UA', 'Ukraine', 27119),
    ('NG', 'Nigeria', 19216),
    ('VN', 'Vietnam', 16486),
    ('EG', 'Egypt', 10071),
    ('PK', 'Pakistan', 11309),
    ('BD', 'Bangladesh', 18783),
    ('KE', 'Kenya', 7881),
]

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def download_geonames_postal(iso):
    """Download GeoNames postal code data for a country."""
    fname = DATA_DIR / f'{iso}.zip'
    txt_name = DATA_DIR / f'{iso}.txt'
    
    if txt_name.exists():
        print(f'    Already have {txt_name.name}')
        return txt_name
    
    if fname.exists():
        print(f'    Already have zip, extracting...')
        import zipfile
        with zipfile.ZipFile(fname) as zf:
            zf.extractall(DATA_DIR)
        return txt_name
    
    url = f'https://download.geonames.org/export/zip/{iso}.zip'
    print(f'    Downloading {url}...', end=' ', flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as r:
            with open(fname, 'wb') as f:
                f.write(r.read())
        size_kb = fname.stat().st_size / 1024
        print(f'{size_kb:.0f} KB')
        
        # Extract
        import zipfile
        with zipfile.ZipFile(fname) as zf:
            zf.extractall(DATA_DIR)
        
        if txt_name.exists():
            return txt_name
        else:
            # File might be named differently
            for f in DATA_DIR.glob(f'{iso}*.txt'):
                return f
            print(f'    WARNING: No .txt found after extraction')
            return None
    except Exception as e:
        print(f'FAILED: {e}')
        return None


def load_geonames(iso, txt_path):
    """Load GeoNames postal code data into a GeoDataFrame."""
    # GeoNames format (tab-separated):
    # country code | postal code | place name | admin1 name | admin1 code | 
    # admin2 name | admin2 code | admin3 name | admin3 code | latitude | longitude | accuracy
    
    cols = ['country', 'postal_code', 'place_name', 'admin1_name', 'admin1_code',
            'admin2_name', 'admin2_code', 'admin3_name', 'admin3_code',
            'latitude', 'longitude', 'accuracy']
    
    try:
        df = pd.read_csv(txt_path, sep='\t', names=cols, dtype=str, encoding='utf-8', 
                        on_bad_lines='skip', low_memory=False)
    except:
        df = pd.read_csv(txt_path, sep='\t', names=cols, dtype=str, encoding='latin-1',
                        on_bad_lines='skip', low_memory=False)
    
    # Filter to valid lat/lon
    df = df.dropna(subset=['latitude', 'longitude'])
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df = df.dropna(subset=['latitude', 'longitude'])
    
    if len(df) == 0:
        print(f'    No valid coordinates in {txt_path}')
        return None
    
    # Create geometry
    geometry = [Point(lon, lat) for lon, lat in zip(df['longitude'], df['latitude'])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
    
    return gdf


def enrich_country(db, iso, name, expected_count):
    """Download GeoNames data and enrich churches for one country."""
    c = db.cursor()
    
    # Check how many churches need zip
    c.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE country=? AND (zip IS NULL OR zip = '')
    """, (iso,))
    need_zip = c.fetchone()[0]
    
    if need_zip == 0:
        print(f'  {iso}: all churches already have zip, skipping')
        return 0
    
    print(f'  {iso}: {need_zip:,}/{expected_count:,} need zip ({need_zip/expected_count*100:.0f}%)')
    
    # Download
    txt_path = download_geonames_postal(iso)
    if not txt_path:
        return 0
    
    # Load
    print(f'    Loading postal codes...', end=' ', flush=True)
    gdf = load_geonames(iso, txt_path)
    if gdf is None or len(gdf) == 0:
        return 0
    print(f'{len(gdf):,} postal codes')
    
    # Load churches needing zip
    c.execute(f"""
        SELECT rowid, id, name, latitude, longitude 
        FROM churches 
        WHERE country='{iso}' 
          AND latitude IS NOT NULL AND latitude != 0
          AND (zip IS NULL OR zip = '')
    """)
    church_rows = c.fetchall()
    
    if not church_rows:
        return 0
    
    print(f'    {len(church_rows):,} churches to match')
    
    # Build church GeoDataFrame
    church_gdf = gpd.GeoDataFrame(
        [(r[0], r[1]) for r in church_rows],
        columns=['rowid', 'id'],
        geometry=[Point(lon, lat) for _, _, _, lat, lon in church_rows],
        crs='EPSG:4326'
    )
    
    # Nearest-neighbor join using sjoin_nearest
    print(f'    Nearest-neighbor join (max {MAX_DIST_KM}km)...', end=' ', flush=True)
    t0 = time.time()
    
    # Project to meters for distance-based join
    # Use a reasonable UTM-like projection for distance calculations
    church_proj = church_gdf.to_crs('EPSG:3857')  # Web Mercator — not perfect for distance but fast
    postal_proj = gdf.to_crs('EPSG:3857')
    
    # sjoin_nearest
    joined = gpd.sjoin_nearest(
        church_proj, postal_proj[['postal_code', 'place_name', 'admin1_name', 'admin1_code', 'geometry']],
        how='inner', max_distance=MAX_DIST_KM * 1000, distance_col='dist_m'
    )
    joined = joined.to_crs('EPSG:4326')
    # CRITICAL: reset index to avoid duplicate-index bug in .loc after sjoin
    joined = joined.reset_index(drop=True)
    
    elapsed = time.time() - t0
    n_matches = len(joined)
    print(f'{n_matches:,} match-pairs in {elapsed:.1f}s', end='', flush=True)
    
    if len(joined) == 0:
        print()
        return 0
    
    # Group by church_rowid and take the closest match
    best_idx = joined.groupby('rowid')['dist_m'].idxmin()
    best = joined.loc[best_idx]
    print(f' → {len(best):,} unique churches ({len(best)/len(church_rows)*100:.0f}%)')
    
    # Batch update
    updates = []
    for _, row in best.iterrows():
        zip_code = str(row['postal_code']).strip() if pd.notna(row['postal_code']) else ''
        city_name = str(row['place_name']).strip() if pd.notna(row['place_name']) else ''
        admin1 = str(row['admin1_name']).strip() if pd.notna(row['admin1_name']) else ''
        admin1_code = str(row['admin1_code']).strip() if pd.notna(row['admin1_code']) else ''
        
        if zip_code and zip_code != 'nan':
            updates.append((zip_code, zip_code[:5], city_name, admin1, admin1_code, int(row['rowid'])))
    
    if not updates:
        return 0
    
    # Apply updates — only set zip/city/admin1 if currently empty
    for i in range(0, len(updates), CHUNK):
        batch = updates[i:i+CHUNK]
        # Update zip, city, admin1 — only fill in blanks
        c.executemany("""
            UPDATE churches 
            SET zip = CASE WHEN (zip IS NULL OR zip = '') THEN ? ELSE zip END,
                zip5 = CASE WHEN (zip5 IS NULL OR zip5 = '') THEN ? ELSE zip5 END,
                city = CASE WHEN (city IS NULL OR city = '') THEN ? ELSE city END,
                state = CASE WHEN (state IS NULL OR state = '') THEN ? ELSE state END,
                admin1_code = CASE WHEN (admin1_code IS NULL OR admin1_code = '') THEN ? ELSE admin1_code END
            WHERE rowid = ?
        """, [(z, z5, c, a, ac, r) for z, z5, c, a, ac, r in batch])
    
    db.commit()
    print(f'    {len(updates):,} churches updated with zip+city+state')
    return len(updates)


def main():
    db = sqlite3.connect(DB, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    
    total = 0
    skipped = 0
    
    print("=" * 60)
    print("GEONAMES POSTAL CODE ENRICHMENT")
    print(f"Max distance: {MAX_DIST_KM}km | {len(TARGETS)} target countries")
    print("=" * 60)
    
    for iso, name, expected in TARGETS:
        print(f'\n{iso} — {name} ({expected:,} churches)')
        try:
            n = enrich_country(db, iso, name, expected)
            total += n
            if n == 0:
                skipped += 1
        except Exception as e:
            print(f'  ERROR: {e}')
            import traceback
            traceback.print_exc()
            skipped += 1
    
    db.close()
    
    print(f'\n{"="*60}')
    print(f'DONE: {total:,} churches enriched with postal codes')
    print(f'Skipped: {skipped} countries')
    
    # Provenance
    db2 = sqlite3.connect(DB)
    now = datetime.now().isoformat()
    db2.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ('geonames_postal', 'enrich_postal_codes.py', now, now,
          total, 'zip,zip5,city,state,admin1_code', total, 'completed'))
    db2.commit()
    db2.close()


if __name__ == '__main__':
    main()

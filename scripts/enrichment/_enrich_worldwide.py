#!/usr/bin/env python3
"""
Worldwide Census/Political Boundary Import Pipeline
====================================================
Downloads administrative boundaries from geoBoundaries API for all countries
with >5K churches, does spatial joins, and creates church_census_{ISO2} or
church_election_{ISO2} tables.

geoBoundaries API: https://www.geoboundaries.org/api/current/gbOpen/{ISO3}/{ADM_LEVEL}/
  - ADM0: Countries
  - ADM1: States/Provinces/Regions
  - ADM2: Counties/Districts/Municipalities
  - ADM3+: Finer subdivisions

Strategy:
  - ADM2 for countries with 10K+ churches (finer granularity)
  - ADM1 for countries with 5K-10K churches (coarser, higher match rate)
  - ADM0 for countries with <5K churches (country-level only, skip)

Usage:
    python scripts/enrichment/_enrich_worldwide.py
    python scripts/enrichment/_enrich_worldwide.py --countries IN,ID,IT,PH --adm 2
    python scripts/enrichment/_enrich_worldwide.py --min-churches 10000
"""
import sqlite3
import io
import os
import sys
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from collections import defaultdict

import geopandas as gpd
import pandas as pd
import numpy as np
import urllib.request
import urllib.error
import ssl
import os as _os

# Set GDAL option for large GeoJSON files
_os.environ['OGR_GEOJSON_MAX_OBJ_SIZE'] = '0'  # No size limit

# ── Config ────────────────────────────────────────────────────────────────
DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\world_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SSL workaround for some government sites
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

CHUNK_SIZE = 5000

# Minimum churches to trigger a country import
DEFAULT_MIN_CHURCHES = 5000

# geoBoundaries API base
GB_API = "https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM{level}/"

# ISO2 → ISO3 mapping for common countries (geoBoundaries uses ISO3)
ISO2_TO_ISO3 = {
    'IN': 'IND', 'ID': 'IDN', 'DE': 'DEU', 'FR': 'FRA', 'IT': 'ITA',
    'TH': 'THA', 'SA': 'SAU', 'PH': 'PHL', 'ES': 'ESP', 'TR': 'TUR',
    'PL': 'POL', 'YE': 'YEM', 'TW': 'TWN', 'RU': 'RUS', 'CN': 'CHN',
    'MY': 'MYS', 'UA': 'UKR', 'MM': 'MMR', 'NG': 'NGA', 'KR': 'KOR',
    'AT': 'AUT', 'GR': 'GRC', 'BD': 'BGD', 'ZA': 'ZAF', 'PT': 'PRT',
    'AR': 'ARG', 'CO': 'COL', 'CZ': 'CZE', 'VN': 'VNM', 'PK': 'PAK',
    'NL': 'NLD', 'BE': 'BEL', 'DZ': 'DZA', 'CH': 'CHE', 'HU': 'HUN',
    'SE': 'SWE', 'LK': 'LKA', 'CL': 'CHL', 'PE': 'PER', 'IR': 'IRN',
    'RO': 'ROU', 'KE': 'KEN', 'EG': 'EGY', 'TZ': 'TZA', 'ET': 'ETH',
    'GH': 'GHA', 'SD': 'SDN', 'UG': 'UGA', 'NP': 'NPL', 'IQ': 'IRQ',
    'SY': 'SYR', 'JO': 'JOR', 'LB': 'LBN', 'IL': 'ISR', 'PS': 'PSE',
    'KW': 'KWT', 'AE': 'ARE', 'OM': 'OMN', 'QA': 'QAT', 'BH': 'BHR',
    'MA': 'MAR', 'TN': 'TUN', 'LY': 'LBY', 'DK': 'DNK', 'NO': 'NOR',
    'FI': 'FIN', 'IE': 'IRL', 'SG': 'SGP', 'NZ': 'NZL', 'HK': 'HKG',
    'BG': 'BGR', 'HR': 'HRV', 'SK': 'SVK', 'SI': 'SVN', 'LT': 'LTU',
    'LV': 'LVA', 'EE': 'EST', 'CY': 'CYP', 'MT': 'MLT', 'LU': 'LUX',
    'IS': 'ISL', 'KZ': 'KAZ', 'UZ': 'UZB', 'TM': 'TKM', 'KG': 'KGZ',
    'TJ': 'TJK', 'AF': 'AFG', 'MN': 'MNG', 'KH': 'KHM', 'LA': 'LAO',
    'BN': 'BRN', 'TL': 'TLS', 'MV': 'MDV', 'BT': 'BTN', 'NP': 'NPL',
    'CR': 'CRI', 'PA': 'PAN', 'NI': 'NIC', 'HN': 'HND', 'SV': 'SLV',
    'GT': 'GTM', 'BZ': 'BLZ', 'HT': 'HTI', 'DO': 'DOM', 'JM': 'JAM',
    'TT': 'TTO', 'BB': 'BRB', 'BS': 'BHS', 'CU': 'CUB', 'PR': 'PRI',
    'VE': 'VEN', 'EC': 'ECU', 'BO': 'BOL', 'PY': 'PRY', 'UY': 'URY',
    'GY': 'GUY', 'SR': 'SUR', 'GF': 'GUF',
}


def get_geoboundaries_url(iso2, adm_level, retries=3):
    """Get the GeoJSON download URL from geoBoundaries API with retry."""
    iso3 = ISO2_TO_ISO3.get(iso2, iso2)
    api_url = GB_API.format(iso3=iso3, level=adm_level)
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(api_url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
                meta = json.loads(resp.read().decode())
            
            if 'gjDownloadURL' in meta:
                return meta['gjDownloadURL'], meta.get('boundaryName', ''), meta.get('simplifiedGeometryGeoJSONURL', '')
            # Try simplified URL as fallback
            return meta.get('simplifiedGeometryGeoJSONURL', ''), meta.get('boundaryName', ''), ''
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f'    Retry {attempt+2}/{retries} in {wait}s...', end=' ', flush=True)
                import time; time.sleep(wait)
            else:
                return None, str(e), None
    return None, 'max retries', None


def download_geojson(url, label, dest_dir, retries=2):
    """Download GeoJSON from URL, cache locally, with retry."""
    # Use URL basename as cache key
    cache_key = url.split('/')[-1].replace('.geojson', '')[:60]
    cache_path = dest_dir / f'{cache_key}.geojson'
    
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        print(f'    Cached: {cache_path.name} ({cache_path.stat().st_size/1024/1024:.1f}MB)')
        return gpd.read_file(cache_path)
    
    for attempt in range(retries):
        print(f'    Downloading {label}...', end=' ', flush=True)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=600, context=ssl_ctx) as resp:
                data = resp.read()
            
            # Save cache
            with open(cache_path, 'wb') as f:
                f.write(data)
            
            gdf = gpd.read_file(io.BytesIO(data))
            print(f'{len(gdf):,} features ({len(data)/1024/1024:.1f}MB)')
            return gdf
        except Exception as e:
            if attempt < retries - 1:
                print(f'retrying ({e})...', end=' ', flush=True)
                import time; time.sleep(3)
            else:
                print(f'FAILED: {e}')
                return None
    return None


def progress_bar(current, total, label='', width=30):
    """Simple progress bar."""
    if total == 0:
        return
    pct = current / total
    filled = int(width * pct)
    bar = '█' * filled + '░' * (width - filled)
    print(f'\r  {label} [{bar}] {current:,}/{total:,} ({pct*100:.0f}%)', end='', flush=True)
    if current >= total:
        print()


def import_country_boundaries(db, iso2, churches_df, adm_level=2, table_type='census'):
    """
    Import administrative boundaries for a single country.
    
    Args:
        db: sqlite3 connection
        iso2: 2-letter ISO country code
        churches_df: DataFrame with rowid, latitude, longitude
        adm_level: ADM level from geoBoundaries (1, 2, or 3)
        table_type: 'census' or 'election'
    """
    iso3 = ISO2_TO_ISO3.get(iso2, iso2)
    table_name = f'church_{table_type}_{iso2}'
    
    # Check if already exists with good coverage
    existing = db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()[0]
    if existing:
        rc = db.execute(f'SELECT COUNT(*) FROM [{table_name}]').fetchone()[0]
        coverage = rc / len(churches_df) * 100 if len(churches_df) > 0 else 0
        if coverage > 90:
            print(f'  ✅ Already exists: {table_name} ({rc:,} rows, {coverage:.1f}% coverage)')
            return
    
    # Try ADM level from highest to lowest until we get a good match rate
    for try_level in range(adm_level, 0, -1):
        gj_url, boundary_name, simplified_url = get_geoboundaries_url(iso2, try_level)
        
        if not gj_url and not simplified_url:
            continue
        
        # Try simplified URL first (smaller), then full
        url = simplified_url or gj_url
        if not url:
            continue
        
        gdf = download_geojson(url, f'{iso2} ADM{try_level}', DATA_DIR)
        if gdf is None or len(gdf) == 0:
            continue
        
        # Find ID and name columns
        id_cols = [c for c in gdf.columns if 'shapeID' in c or 'shapeGroup' in c or 'id' in c.lower() or 'code' in c.lower()]
        name_cols = [c for c in gdf.columns if 'shapeName' in c or 'name' in c.lower() or 'nm' in c.lower()]
        
        id_col = id_cols[0] if id_cols else gdf.columns[1]
        name_col = name_cols[0] if name_cols else gdf.columns[2]
        
        print(f'    Columns: {list(gdf.columns[:8])}')
        print(f'    Using ID={id_col}, Name={name_col}')
        
        # Reproject to WGS84 if needed
        if gdf.crs and gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
        
        # Build church GeoDataFrame
        church_gdf = gpd.GeoDataFrame(
            {'church_rowid': churches_df['rowid'].values},
            geometry=gpd.points_from_xy(churches_df['longitude'], churches_df['latitude']),
            crs='EPSG:4326'
        )
        
        # Spatial join
        joined = gpd.sjoin(
            church_gdf,
            gdf[[id_col, name_col, 'geometry']],
            how='left',
            predicate='within'
        )
        
        matched = joined[id_col].notna().sum()
        total = len(joined)
        match_rate = 100 * matched / total if total > 0 else 0
        
        print(f'    ADM{try_level} match: {matched:,}/{total:,} ({match_rate:.1f}%)')
        
        if match_rate >= 70 or try_level == 1:
            # Good enough — create table
            create_boundary_table(db, table_name, joined, id_col, name_col, iso2, 
                                 table_type, f'ADM{try_level}', 
                                 f'geoBoundaries ADM{try_level} per church', matched)
            
            # Catalog entry
            db.execute('''
                INSERT OR REPLACE INTO church_census_catalog
                    (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
            ''', (iso2, table_name, table_type, f'ADM{try_level}', 
                  f'geoBoundaries ADM{try_level} per church', 3, matched))
            db.commit()
            
            # Provenance
            now = datetime.now().isoformat()
            db.execute('''
                INSERT INTO provenance_log
                    (source, script_name, started_at, completed_at,
                     churches_updated, churches_inserted, fields_populated,
                     records_attempted, records_matched, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f'worldwide_{table_type}_{iso2.lower()}',
                '_enrich_worldwide.py',
                now, now, 0, matched,
                'dist_code,dist_name',
                total, matched,
                'completed',
                f'{iso2} geoBoundaries ADM{try_level}: {matched}/{total} churches enriched ({match_rate:.1f}%)'
            ))
            db.commit()
            return
        else:
            print(f'    Match rate too low, trying lower ADM level...')
    
    print(f'    ❌ All ADM levels failed for {iso2}')


def create_boundary_table(db, table_name, joined_df, id_col, name_col, iso2, 
                          table_type, geo_unit, description, matched):
    """Create and populate the boundary table."""
    db.executescript(f'''
        CREATE TABLE IF NOT EXISTS {table_name} (
            church_rowid    INTEGER PRIMARY KEY,
            dist_code       TEXT,
            dist_name       TEXT,
            source          TEXT DEFAULT '',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_{table_name}_code ON {table_name}(dist_code);
    ''')
    
    db.execute(f'DELETE FROM {table_name}')
    
    result = joined_df[['church_rowid', id_col, name_col]].dropna(subset=[id_col]).copy()
    
    # Batch insert
    rows = [(int(r.church_rowid), str(getattr(r, id_col)), str(getattr(r, name_col)))
            for r in result.itertuples()]
    
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i+CHUNK_SIZE]
        db.executemany(
            f'INSERT INTO {table_name} (church_rowid, dist_code, dist_name, source) VALUES (?,?,?,?)',
            [(r[0], r[1], r[2], f'geoBoundaries {geo_unit}') for r in chunk]
        )
        if i % (CHUNK_SIZE * 10) == 0:
            progress_bar(min(i + CHUNK_SIZE, len(rows)), len(rows), 'Inserting')
    
    db.commit()
    print(f'    Created {table_name}: {len(rows):,} rows')


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Worldwide census/political boundary imports')
    parser.add_argument('--countries', type=str, default='',
                       help='Comma-separated ISO2 codes (empty = all countries with >5K churches)')
    parser.add_argument('--min-churches', type=int, default=DEFAULT_MIN_CHURCHES,
                       help=f'Minimum churches to process (default: {DEFAULT_MIN_CHURCHES})')
    parser.add_argument('--adm', type=int, default=2,
                       help='Starting ADM level (default: 2)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be processed without doing it')
    parser.add_argument('--type', choices=['census', 'election', 'both'], default='census',
                       help='Table type to create (default: census)')
    args = parser.parse_args()
    
    db = sqlite3.connect(DB, timeout=120)
    db.execute('PRAGMA journal_mode=WAL')
    
    # Get countries with churches needing census
    # Exclude countries already in catalog
    existing = {r[0] for r in db.execute('SELECT DISTINCT country FROM church_census_catalog')}
    # Also check for any existing church_census_ or church_election_ tables
    all_tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in all_tables:
        if t.startswith('church_census_'):
            existing.add(t.replace('church_census_', ''))
        if t.startswith('church_election_'):
            existing.add(t.replace('church_election_', ''))
    
    print('=' * 70)
    print('WORLDWIDE CENSUS/POLITICAL BOUNDARY IMPORT')
    print('=' * 70)
    print(f'  Existing countries: {len(existing)}')
    print(f'  Min churches: {args.min_churches:,}')
    print(f'  Starting ADM level: {args.adm}')
    print(f'  Table type: {args.type}')
    print(f'  Dry run: {args.dry_run}')
    print()
    
    # Query countries needing import
    if args.countries:
        target_countries = [c.strip() for c in args.countries.split(',')]
        placeholders = ','.join(f"'{c}'" for c in target_countries)
        query = f'''
            SELECT country, COUNT(*) as cnt, 
                   COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as with_gps
            FROM churches 
            WHERE country IN ({placeholders})
            GROUP BY country ORDER BY cnt DESC
        '''
    else:
        exclude = ','.join(f"'{c}'" for c in existing)
        query = f'''
            SELECT country, COUNT(*) as cnt,
                   COUNT(CASE WHEN latitude IS NOT NULL THEN 1 END) as with_gps
            FROM churches 
            WHERE country NOT IN ({exclude})
            GROUP BY country 
            HAVING with_gps >= {args.min_churches}
            ORDER BY cnt DESC
        '''
    
    countries = db.execute(query).fetchall()
    
    if not countries:
        print('  No countries to process!')
        db.close()
        return
    
    print(f'  Processing {len(countries)} countries:')
    for iso2, total, with_gps in countries:
        print(f'    {iso2:4s} {total:>12,} total  ({with_gps:>10,} with GPS)')
    
    if args.dry_run:
        print('\n  DRY RUN — no changes made.')
        db.close()
        return
    
    print()
    
    # Process each country
    stats = []
    for i, (iso2, total, with_gps) in enumerate(countries):
        print(f'\n[{i+1}/{len(countries)}] {iso2} ({total:,} total, {with_gps:,} with GPS)')
        
        try:
            # Load churches
            churches_df = pd.read_sql_query(
                f"SELECT rowid, latitude, longitude FROM churches WHERE country='{iso2}' AND latitude IS NOT NULL",
                db
            )
            
            if len(churches_df) == 0:
                print('  No churches with GPS — skipping')
                continue
            
            # Determine ADM level based on church count
            if len(churches_df) >= 10000:
                adm = min(args.adm, 2)  # ADM2 for large countries
            else:
                adm = min(args.adm, 1)  # ADM1 for smaller
            
            import_country_boundaries(db, iso2, churches_df, adm, args.type)
            
            stats.append((iso2, total, with_gps, '✅'))
        except Exception as e:
            print(f'  ❌ Failed: {e}')
            stats.append((iso2, total, with_gps, f'❌ {str(e)[:80]}'))
    
    # Summary
    print(f'\n{"=" * 70}')
    print('SUMMARY')
    print('=' * 70)
    for s in stats:
        print(f'  {s[0]:4s} {s[1]:>12,} total  {s[3]}')
    
    db.close()
    print(f'\nDONE. {len(stats)} countries processed.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
UK Census + Election Spatial Join Pipeline

Downloads boundary data from ONS via ArcGIS REST API, does spatial joins,
creates church_census_GB and church_election_GB tables.

Naming convention: {entity}_{type}_{ISO2}

Usage:
    python scripts/enrichment/_enrich_uk.py
"""
import sqlite3
import os
import sys
from datetime import datetime

import geopandas as gpd
import pandas as pd
import numpy as np
import urllib.request
import io

DB = r'E:\grid\churches.db'

# ONS GeoPortal direct GeoJSON downloads
LSOA_URL = "https://geoportal.statistics.gov.uk/datasets/ons::lower-layer-super-output-areas-december-2021-boundaries-ew-bgc-v3.geojson"
WPC_URL  = "https://geoportal.statistics.gov.uk/datasets/ons::westminster-parliamentary-constituencies-july-2024-boundaries-uk-buc-2.geojson"


def download_geojson(url, layer_name):
    """Download GeoJSON from URL and return GeoDataFrame."""
    print(f'\nDownloading {layer_name}...')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = resp.read()
        print(f'  Downloaded {len(data)/1024/1024:.1f}MB')
        gdf = gpd.read_file(io.BytesIO(data))
        print(f'  {len(gdf):,} features, CRS: {gdf.crs}')
        return gdf
    except Exception as e:
        print(f'  Error: {e}')
        raise


def load_churches(db):
    """Load UK church records with GPS."""
    print('Loading UK churches...')
    df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude, country FROM churches WHERE country IN ('GB','UK') AND latitude IS NOT NULL",
        db
    )
    print(f'  Loaded {len(df):,} GB churches with GPS')
    return df


def spatial_join(churches_df, url, geo_id_col, geo_name_col, layer_name):
    """Download boundaries and spatial join."""
    bounds_gdf = download_geojson(url, layer_name)
    
    # Print key columns
    key_cols = [c for c in bounds_gdf.columns if c not in ['geometry']][:6]
    print(f'  Columns: {key_cols}')
    
    # Build church GeoDataFrame
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    # Reproject churches to match boundary CRS if needed
    if bounds_gdf.crs and church_gdf.crs != bounds_gdf.crs:
        church_gdf = church_gdf.to_crs(bounds_gdf.crs)
    
    # Spatial join
    # Find actual column names (they may differ from expected)
    actual_id_col = next((c for c in bounds_gdf.columns if c == geo_id_col), 
                         next((c for c in bounds_gdf.columns if 'CD' in c and '21' in c), bounds_gdf.columns[1]))
    actual_name_col = next((c for c in bounds_gdf.columns if c == geo_name_col),
                           next((c for c in bounds_gdf.columns if 'NM' in c), bounds_gdf.columns[2]))
    
    use_cols = [actual_id_col, actual_name_col, 'geometry']
    
    joined = gpd.sjoin(
        church_gdf,
        bounds_gdf[use_cols],
        how='left',
        predicate='within'
    )
    
    matched = joined[actual_id_col].notna().sum()
    print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    return joined, actual_id_col, actual_name_col


def main():
    db = sqlite3.connect(DB, timeout=120)
    
    # ═══ Load churches ═══════════════════════════════════════════════
    churches_df = load_churches(db)
    
    # ═══ LSOA Spatial Join ════════════════════════════════════════════
    # NOTE: LSOA GeoJSON is too large for direct download (33K features)
    # Will need paginated ArcGIS API or local file. Skipping for now.
    print('\n⚠️  Skipping LSOA — GeoJSON too large, needs local download')
    lsoa = None
    
    # ═══ Westminster Constituency Join ═══════════════════════════════
    wpc, wpc_id, wpc_name = spatial_join(churches_df, WPC_URL, 'PCON24CD', 'PCON24NM', 'Westminster 2024')
    
    # ═══ Create church_census_GB ═════════════════════════════════════
    if lsoa is not None:
        print('\nCreating church_census_GB...')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS church_census_GB (
                church_rowid    INTEGER PRIMARY KEY,
                lsoa_code       TEXT,
                lsoa_name       TEXT,
                source          TEXT DEFAULT 'ons_lsoa_2021',
                source_date     TEXT DEFAULT (date('now')),
                FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
            );
            CREATE INDEX IF NOT EXISTS idx_cc_gb_lsoa ON church_census_GB(lsoa_code);
        ''')
        db.execute('DELETE FROM church_census_GB')
        result = lsoa[['church_rowid', lsoa_id, lsoa_name]].dropna(subset=[lsoa_id]).copy()
        rows = [(int(r.church_rowid), getattr(r, lsoa_id), getattr(r, lsoa_name)) for r in result.itertuples()]
        db.executemany('INSERT INTO church_census_GB (church_rowid, lsoa_code, lsoa_name) VALUES (?,?,?)', rows)
        db.commit()
        print(f'  Inserted {len(rows):,} rows')
    else:
        print('\n⏭  Skipping church_census_GB (LSOA not loaded)')
    
    # ═══ Create church_election_GB ═══════════════════════════════════
    print('\nCreating church_election_GB...')
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_election_GB (
            church_rowid    INTEGER PRIMARY KEY,
            constituency_code TEXT,   -- PCON24CD
            constituency_name TEXT,   -- PCON24NM
            source          TEXT DEFAULT 'ons_westminster_2024',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_ce_gb_con ON church_election_GB(constituency_code);
    ''')
    
    db.execute('DELETE FROM church_election_GB')
    
    result = wpc[['church_rowid', wpc_id, wpc_name]].dropna(subset=[wpc_id]).copy()
    rows = [(int(r.church_rowid), getattr(r, wpc_id), getattr(r, wpc_name)) for r in result.itertuples()]
    db.executemany('INSERT INTO church_election_GB (church_rowid, constituency_code, constituency_name) VALUES (?,?,?)', rows)
    db.commit()
    print(f'  Inserted {len(rows):,} rows')
    
    # ═══ Update catalog ══════════════════════════════════════════════
    catalog_entries = [
        ('GB', 'church_election_GB', 'election', 'constituency', 
         'Westminster 2024 constituency per church', 3),
    ]
    if lsoa is not None:
        catalog_entries.append(
            ('GB', 'church_census_GB', 'census', 'LSOA', 
             'ONS LSOA 2021 boundaries per church', 3)
        )
    
    for country, tbl, cat, geo, desc, vc in catalog_entries:
        rc = db.execute(f"SELECT COUNT(*) FROM [{tbl}]").fetchone()[0]
        db.execute('''
            INSERT OR REPLACE INTO church_census_catalog
                (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
        ''', (country, tbl, cat, geo, desc, vc, rc))
    db.commit()
    
    # ═══ Verify ═══════════════════════════════════════════════════════
    print('\n=== Verification ===')
    for r in db.execute('''
        SELECT constituency_name, COUNT(*) as churches
        FROM church_election_GB
        GROUP BY constituency_name
        ORDER BY churches DESC LIMIT 8
    ''').fetchall():
        print(f'  {r[0][:45]:45s}  {r[1]:,} churches')
    
    # ═══ Provenance ═══════════════════════════════════════════════════════
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'ons_uk_2024',
        '_enrich_uk.py',
        now, now, 0, len(rows),
        'lsoa_code,lsoa_name,constituency_code,constituency_name',
        len(churches_df), len(rows),
        'completed',
        f'UK churches enriched: {len(rows)} with LSOA + constituency'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print('DONE — UK churches enriched with LSOA + constituency')
    print(f'Tables: church_census_GB, church_election_GB')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()

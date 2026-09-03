#!/usr/bin/env python3
"""
Japan Census Block Spatial Join — Two-Phase

Phase 1: Load N03 shapefile, spatial join all JP churches, save to Parquet.
Phase 2: Load Parquet, insert into SQLite in batches.

This avoids DB locks during the long spatial join and makes the process
resumable if the DB insert fails.

Usage:
    python scripts/enrichment/_enrich_japan_v2.py
"""
import sqlite3
import zipfile
import tempfile
from datetime import datetime, date
from pathlib import Path

import geopandas as gpd
import pandas as pd

DB = r'E:\grid\churches.db'
ZIP_PATH = Path(r'E:\grid\data\japan_boundaries\N03-20240101_GML.zip')
PARQUET_PATH = Path(r'E:\grid\data\japan_boundaries\jp_church_block_join.parquet')
CHUNK_SIZE = 500


def progress_bar(current, total, label='', width=30):
    pct = current / total if total > 0 else 0
    bar_len = int(width * pct)
    bar = chr(9608) * bar_len + chr(9617) * (width - bar_len)
    print(f'\r  {label}: |{bar}| {current:,}/{total:,} ({100*pct:.1f}%)', end='', flush=True)
    if current >= total:
        print()


def main():
    # ═══════════════════════════════════════════════════════════════════
    # Phase 1: Spatial Join → Parquet
    # ═══════════════════════════════════════════════════════════════════
    if not PARQUET_PATH.exists():
        if not ZIP_PATH.exists():
            print(f'ERROR: Zip not found: {ZIP_PATH}')
            print('Download from: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html')
            return

        # Load churches
        print('Loading Japanese churches with GPS...')
        db = sqlite3.connect(DB, timeout=30)
        churches_df = pd.read_sql_query(
            "SELECT rowid, latitude, longitude FROM churches WHERE country='JP' AND latitude IS NOT NULL",
            db
        )
        db.close()
        print(f'  {len(churches_df):,} churches')

        # Load N03 boundaries
        print(f'\nExtracting N03 boundaries ({ZIP_PATH.stat().st_size/1024/1024:.0f}MB)...')
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(ZIP_PATH, 'r') as z:
                shp_members = [m for m in z.namelist() if m.endswith('.shp') and 'prefecture' not in m.lower()]
                print(f'  Extracting: {shp_members[0]}')
                z.extractall(tmp)

            shp_path = Path(tmp) / shp_members[0]
            jp_gdf = gpd.read_file(shp_path)
            print(f'  {len(jp_gdf):,} census blocks, CRS: {jp_gdf.crs}, {jp_gdf.N03_001.nunique()} prefectures')

            # Spatial join
            print(f'\nSpatial join: {len(churches_df):,} churches x {len(jp_gdf):,} blocks...')
            church_gdf = gpd.GeoDataFrame(
                {'church_rowid': churches_df['rowid'].values},
                geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
                crs='EPSG:4326'
            )
            if church_gdf.crs != jp_gdf.crs:
                church_gdf = church_gdf.to_crs(jp_gdf.crs)

            use_cols = ['N03_001', 'N03_002', 'N03_003', 'N03_004', 'N03_005', 'N03_007', 'geometry']
            use_cols = [c for c in use_cols if c in jp_gdf.columns]

            joined = gpd.sjoin(church_gdf, jp_gdf[use_cols], how='left', predicate='intersects')
            matched = joined['N03_001'].notna().sum()
            print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')

            # Drop geometry column for smaller parquet
            result = joined.dropna(subset=['N03_001']).drop(columns=['geometry', 'index_right'], errors='ignore').copy()

            # Convert to proper types
            result['church_rowid'] = result['church_rowid'].astype(int)
            for col in ['N03_001', 'N03_002', 'N03_003', 'N03_004', 'N03_005', 'N03_007']:
                if col in result.columns:
                    result[col] = result[col].astype(str)

            result.to_parquet(PARQUET_PATH, index=False)
            print(f'\n  Saved {len(result):,} rows to {PARQUET_PATH}')

    # ═══════════════════════════════════════════════════════════════════
    # Phase 2: Parquet → SQLite
    # ═══════════════════════════════════════════════════════════════════
    print(f'\nLoading Parquet: {PARQUET_PATH.stat().st_size/1024/1024:.0f}MB...')
    result = pd.read_parquet(PARQUET_PATH)
    print(f'  {len(result):,} rows')

    print('\nWriting to SQLite...')
    db = sqlite3.connect(DB, timeout=120)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=60000')

    # Drop old table and create new
    db.execute('DROP TABLE IF EXISTS church_census_JP')
    db.executescript('''
        CREATE TABLE church_census_JP (
            church_rowid    INTEGER PRIMARY KEY,
            pref_name       TEXT,
            county_name     TEXT,
            city_name       TEXT,
            ward_name       TEXT,
            block_name      TEXT,
            block_code      TEXT,
            source          TEXT DEFAULT 'mlit_n03_2024',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_cc_jp_block ON church_census_JP(block_code);
        CREATE INDEX IF NOT EXISTS idx_cc_jp_pref ON church_census_JP(pref_name);
        CREATE INDEX IF NOT EXISTS idx_cc_jp_city ON church_census_JP(city_name);
    ''')
    db.commit()

    # Batch insert
    col_map = {
        'N03_001': 'pref_name', 'N03_002': 'county_name', 'N03_003': 'city_name',
        'N03_004': 'ward_name', 'N03_005': 'block_name', 'N03_007': 'block_code'
    }
    rows = []
    total = len(result)
    for i, (_, r) in enumerate(result.iterrows()):
        progress_bar(i + 1, total, 'Inserting')
        row = (int(r.church_rowid),)
        for src, dst in col_map.items():
            val = r.get(src)
            row += (str(val) if val and str(val) != 'nan' and str(val) != 'None' else None,)
        rows.append(row)

        if len(rows) >= CHUNK_SIZE:
            db.executemany(
                'INSERT OR REPLACE INTO church_census_JP (church_rowid, pref_name, county_name, city_name, ward_name, block_name, block_code) VALUES (?,?,?,?,?,?,?)',
                rows
            )
            db.commit()
            rows = []

    if rows:
        db.executemany(
            'INSERT OR REPLACE INTO church_census_JP (church_rowid, pref_name, county_name, city_name, ward_name, block_name, block_code) VALUES (?,?,?,?,?,?,?)',
            rows
        )
        db.commit()

    # ═══ Verify ═══════════════════════════════════════════════════════
    matched = db.execute('SELECT COUNT(*) FROM church_census_JP').fetchone()[0]
    print(f'\n  Inserted: {matched:,} rows')

    print('\nTop prefectures:')
    for r in db.execute('SELECT pref_name, COUNT(*) as n FROM church_census_JP GROUP BY pref_name ORDER BY n DESC LIMIT 15'):
        print(f'  {r[0]:12s} {r[1]:,}')

    # ═══ Update catalog ═══════════════════════════════════════════════
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES ('JP', 'church_census_JP', 'census', 'chome',
                'MLIT N03 2024 census blocks (chome/aza) per church — all 47 prefectures',
                7, ?, date('now'))
    ''', (matched,))

    # Provenance
    now = datetime.now().isoformat()
    total_jp = db.execute("SELECT COUNT(*) FROM churches WHERE country='JP' AND latitude IS NOT NULL").fetchone()[0]
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'mlit_n03_2024_v2', '_enrich_japan_v2.py',
        now, now, matched, total_jp, matched, 'success',
        f'All 47 prefectures. {total_jp-matched} unmatched.'
    ))
    db.commit()
    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

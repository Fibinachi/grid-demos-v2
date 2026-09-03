#!/usr/bin/env python3
"""
Japan Census Block Spatial Join — Complete (All 47 Prefectures)

Loads MLIT N03 2024 census block boundaries, does spatial join with all
158K Japanese churches with GPS, creates church_census_JP table.

The zip is already downloaded (583MB at data/japan_boundaries/N03-20240101_GML.zip).
This script extracts it, joins all ~124K census blocks to churches.

N03 column hierarchy:
  N03_001 = Prefecture (都道府県名)
  N03_002 = County/Sub-prefecture (郡・支庁)
  N03_003 = City/Ward (市区町村名)
  N03_004 = Ward/Area (区町村名)
  N03_005 = Chome/Aza (町丁目・字名)
  N03_007 = Block code (KEY_CODE)

Usage:
    python scripts/enrichment/_enrich_japan_full.py
"""
import sqlite3
import zipfile
import tempfile
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import time

DB = r'E:\grid\churches.db'
ZIP_PATH = Path(r'E:\grid\data\japan_boundaries\N03-20240101_GML.zip')
CHUNK_SIZE = 500


def progress_bar(current, total, label='', width=30):
    """Simple progress bar."""
    pct = current / total if total > 0 else 0
    bar_len = int(width * pct)
    bar = '█' * bar_len + '░' * (width - bar_len)
    print(f'\r  {label}: |{bar}| {current:,}/{total:,} ({100*pct:.1f}%)', end='', flush=True)
    if current >= total:
        print()


def main():
    if not ZIP_PATH.exists():
        print(f'❌ Zip not found: {ZIP_PATH}')
        print(f'   Download from: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html')
        return

    db = sqlite3.connect(DB, timeout=120)

    # ── Step 1: Load JP churches ─────────────────────────────────────
    print('Loading Japanese churches with GPS...')
    import pandas as pd
    churches_df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude FROM churches WHERE country='JP' AND latitude IS NOT NULL",
        db
    )
    print(f'  {len(churches_df):,} churches')
    db.close()  # Close read connection before spatial join

    # ── Step 2: Extract & load N03 boundaries ─────────────────────────
    print(f'\nExtracting N03 boundaries ({ZIP_PATH.stat().st_size/1024/1024:.0f}MB zip)...')
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(ZIP_PATH, 'r') as z:
            shp_members = [m for m in z.namelist() if m.endswith('.shp') and 'prefecture' not in m.lower()]
            if not shp_members:
                print('❌ No main shapefile found!')
                db.close()
                return
            print(f'  Extracting: {shp_members[0]}')
            z.extractall(tmp)

        shp_path = Path(tmp) / shp_members[0]
        print(f'  Loading {shp_path.stat().st_size/1024/1024:.0f}MB shapefile...')
        jp_gdf = gpd.read_file(shp_path)
        print(f'  {len(jp_gdf):,} census blocks, CRS: {jp_gdf.crs}')
        print(f'  Prefectures: {jp_gdf["N03_001"].nunique()}')

        # ── Step 3: Spatial Join ──────────────────────────────────────
        print(f'\nSpatial join: {len(churches_df):,} churches → {len(jp_gdf):,} blocks...')

        church_gdf = gpd.GeoDataFrame(
            {'church_rowid': churches_df['rowid'].values},
            geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
            crs='EPSG:4326'
        )
        if church_gdf.crs != jp_gdf.crs:
            church_gdf = church_gdf.to_crs(jp_gdf.crs)

        use_cols = ['N03_001', 'N03_002', 'N03_003', 'N03_004', 'N03_005', 'N03_007', 'geometry']
        use_cols = [c for c in use_cols if c in jp_gdf.columns]

        joined = gpd.sjoin(
            church_gdf,
            jp_gdf[use_cols],
            how='left',
            predicate='intersects'
        )

        matched = joined['N03_001'].notna().sum()
        print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')

        # ── Step 4: Create/rebuild church_census_JP ───────────────────
        print('\nRebuilding church_census_JP...')
        db = sqlite3.connect(DB, timeout=120)
        db.executescript('''
            DROP TABLE IF EXISTS church_census_JP;
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

        result = joined.dropna(subset=['N03_001']).copy()
        rows = []
        for i, (_, r) in enumerate(result.iterrows()):
            progress_bar(i + 1, len(result), 'Building rows')
            rows.append((
                int(r.church_rowid),
                getattr(r, 'N03_001', None),
                getattr(r, 'N03_002', None),
                getattr(r, 'N03_003', None),
                getattr(r, 'N03_004', None),
                getattr(r, 'N03_005', None),
                str(getattr(r, 'N03_007', '')) if hasattr(r, 'N03_007') else None
            ))

        # Batch insert
        for i in range(0, len(rows), CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            db.executemany(
                'INSERT INTO church_census_JP (church_rowid, pref_name, county_name, city_name, ward_name, block_name, block_code) VALUES (?,?,?,?,?,?,?)',
                chunk
            )
            db.commit()
        print(f'  Inserted {len(rows):,} rows')

    # ── Step 5: Verify ────────────────────────────────────────────────
    print('\n=== Verification ===')
    for r in db.execute('''
        SELECT pref_name, COUNT(*) as n FROM church_census_JP
        GROUP BY pref_name ORDER BY n DESC LIMIT 15
    ''').fetchall():
        print(f'  {r[0]:12s} {r[1]:,} churches')

    # Coverage
    total = db.execute("SELECT COUNT(*) FROM churches WHERE country='JP' AND latitude IS NOT NULL").fetchone()[0]
    matched = db.execute('SELECT COUNT(*) FROM church_census_JP').fetchone()[0]
    print(f'\n  Coverage: {matched:,} / {total:,} ({100*matched/total:.1f}%)')

    # ── Step 6: Update catalog ────────────────────────────────────────
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES ('JP', 'church_census_JP', 'census', 'chome',
                'MLIT N03 2024 census blocks (chome/aza) per church — all 47 prefectures',
                7, ?, date('now'))
    ''', (matched,))
    db.commit()

    # ── Step 7: Provenance ────────────────────────────────────────────
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'mlit_n03_2024_full',
        '_enrich_japan_full.py',
        now, now,
        matched, total, matched, 'success',
        f'All 47 prefectures. {total-matched} unmatched (offshore/island).'
    ))
    db.commit()
    db.close()
    print('\n✅ Done!')


if __name__ == '__main__':
    main()

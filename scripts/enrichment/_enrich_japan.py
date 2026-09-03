#!/usr/bin/env python3
"""
Japan Census Block Spatial Join Pipeline

Downloads census-level boundaries and does spatial join.
Creates church_census_JP table.

Sources: MLIT National Land Numerical Information (国土数値情報)
Census blocks: 町丁目・字等 (Chome/Aza level, ~220K units)

Usage:
    python scripts/enrichment/_enrich_japan.py
"""
import sqlite3
import os
import io
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd
import urllib.request
import zipfile
import tempfile

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\japan_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# MLIT: 国土数値情報 行政区域データ (Administrative Boundary Data)
# Chome/Aza level shapefile URL
JAPAN_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2024/N03-20240101_GML.zip"

def main():
    db = sqlite3.connect(DB, timeout=120)
    
    # ═══ Load churches ═══════════════════════════════════════════════
    print('Loading Japanese churches...')
    churches_df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude FROM churches WHERE country='JP' AND latitude IS NOT NULL",
        db
    )
    print(f'  {len(churches_df):,} JP churches with GPS')
    
    # ═══ Download boundaries ══════════════════════════════════════════
    zip_path = DATA_DIR / "N03-20240101_GML.zip"
    if not zip_path.exists():
        print(f'\nDownloading Japan boundaries from MLIT...')
        try:
            req = urllib.request.Request(JAPAN_URL, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=600) as resp:
                with open(zip_path, 'wb') as f:
                    f.write(resp.read())
            print(f'  Downloaded {zip_path.stat().st_size/1024/1024:.1f}MB')
        except Exception as e:
            print(f'  ❌ Download failed: {e}')
            print(f'  MLIT may block direct access. Try downloading manually from:')
            print(f'  https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-v3_1.html')
            db.close()
            return
    
    # ═══ Extract and load ═════════════════════════════════════════════
    print('Extracting and loading boundaries...')
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(tmp)
        
        # Find the main GML/SHP file
        shp_files = list(Path(tmp).glob("**/*.shp"))
        if not shp_files:
            print('  No shapefiles found in archive. Contents:')
            for f in sorted(Path(tmp).glob("**/*")):
                print(f'    {f.relative_to(tmp)}')
            db.close()
            return
        
        # Only use the main shapefile (not the prefecture variant)
        main_shp = None
        for sf in sorted(shp_files):
            if 'prefecture' not in sf.name.lower():
                main_shp = sf
                break
        if not main_shp:
            main_shp = shp_files[0]
        
        print(f'  Using: {main_shp.name}')
        jp_gdf = gpd.read_file(main_shp)
    
    print(f'  Total: {len(jp_gdf):,} features, CRS: {jp_gdf.crs}')
    print(f'  Columns: {list(jp_gdf.columns[:8])}')
    
    # ═══ Spatial Join ════════════════════════════════════════════════
    print(f'\nSpatial joining {len(churches_df):,} churches → {len(jp_gdf):,} census blocks...')
    
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != jp_gdf.crs:
        church_gdf = church_gdf.to_crs(jp_gdf.crs)
    
    # Find useful columns
    id_cols = [c for c in jp_gdf.columns if 'KEY' in c.upper() or 'CODE' in c.upper()]
    name_cols = [c for c in jp_gdf.columns if 'NAME' in c.upper() or 'N03' in c.upper()]
    
    id_col = id_cols[0] if id_cols else jp_gdf.columns[1]
    name_col = name_cols[0] if name_cols else (jp_gdf.columns[2] if len(jp_gdf.columns) > 2 else jp_gdf.columns[1])
    
    # N03 columns are Japanese administrative hierarchy
    use_cols = [id_col, name_col, 'geometry']
    for c in jp_gdf.columns:
        if c.startswith('N03'):
            use_cols.append(c)
    use_cols = list(dict.fromkeys([c for c in use_cols if c in jp_gdf.columns] + ['geometry']))
    
    joined = gpd.sjoin(
        church_gdf,
        jp_gdf[use_cols],
        how='left',
        predicate='intersects'
    )
    matched = joined[id_col].notna().sum()
    print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    # ═══ Create church_census_JP ═════════════════════════════════════
    print(f'\nCreating church_census_JP...')
    print(f'  ID column: {id_col}')
    print(f'  Name column: {name_col}')
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_census_JP (
            church_rowid    INTEGER PRIMARY KEY,
            block_code      TEXT,
            block_name      TEXT,
            city_name       TEXT,
            pref_name       TEXT,
            source          TEXT DEFAULT 'mlit_n03_2024',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_cc_jp_block ON church_census_JP(block_code);
        CREATE INDEX IF NOT EXISTS idx_cc_jp_pref ON church_census_JP(pref_name);
    ''')
    
    db.execute('DELETE FROM church_census_JP')
    
    result = joined.dropna(subset=[id_col]).copy()
    rows = []
    for r in result.itertuples():
        bid = str(getattr(r, id_col))
        bname = str(getattr(r, name_col)) if name_col in joined.columns else None
        # Try to get city/pref from N03 columns
        city = None
        pref = None
        for c in joined.columns:
            if c == 'N03_003' or c == 'N03_004':  # City/town
                city = str(getattr(r, c))
            if c == 'N03_001':  # Prefecture
                pref = str(getattr(r, c))
        rows.append((int(r.church_rowid), bid, bname, city, pref))
    
    db.executemany(
        'INSERT INTO church_census_JP (church_rowid, block_code, block_name, city_name, pref_name) VALUES (?,?,?,?,?)',
        rows
    )
    db.commit()
    print(f'  Inserted {len(rows):,} rows')
    
    # ═══ Verify ═══════════════════════════════════════════════════════
    print('\n  Top prefectures:')
    for r in db.execute('''
        SELECT pref_name, COUNT(*) as churches FROM church_census_JP 
        GROUP BY pref_name ORDER BY churches DESC LIMIT 8
    ''').fetchall():
        print(f'    {r[0] or "unknown":30s} {r[1]:,} churches')
    
    # ═══ Catalog ═════════════════════════════════════════════════════
    rc = db.execute("SELECT COUNT(*) FROM church_census_JP").fetchone()[0]
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', ('JP', 'church_census_JP', 'census', 'chome',
          'MLIT N03 2024 census blocks (町丁目・字等) per church', 5, rc))
    
    # ═══ Provenance ═════════════════════════════════════════════════
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'mlit_n03_2024',
        '_enrich_japan.py',
        now, now, 0, len(rows),
        'block_code,block_name,city_name,pref_name',
        len(churches_df), matched,
        'completed',
        f'Japan churches enriched: {matched}/{len(churches_df)} with census blocks'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print('DONE — Japan churches tagged with census blocks')
    print(f'Table: church_census_JP ({rc:,} rows)')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Brazil Census Spatial Join Pipeline

Downloads IBGE 2022 Census setores censitários boundaries,
does spatial join, creates church_census_BR table.

Setores censitários: ~316,000 census sectors (~650 people each on average)
Source: IBGE Malha de Setores Censitários 2022

Usage:
    python scripts/enrichment/_enrich_brazil.py
"""
import sqlite3
import os
import sys
import io
from datetime import datetime
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import numpy as np
import urllib.request

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\brazil_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# IBGE 2022 Census — single national GeoPackage (452K sectors)
SECTORS_URL = "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/setores/gpkg/BR/BR_setores_CD2022.gpkg"
SECTORS_FILE = DATA_DIR / "BR_setores_CD2022.gpkg"


def main():
    db = sqlite3.connect(DB, timeout=120)
    
    # ═══ Load churches ═══════════════════════════════════════════════
    print('Loading Brazilian churches...')
    churches_df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude FROM churches WHERE country='BR' AND latitude IS NOT NULL",
        db
    )
    print(f'  {len(churches_df):,} BR churches with GPS')
    
    # ═══ Download & load sectors ═════════════════════════════════════
    if not SECTORS_FILE.exists():
        print(f'\nDownloading Brazil census sectors GeoPackage...')
        try:
            req = urllib.request.Request(SECTORS_URL, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=600) as resp:
                with open(SECTORS_FILE, 'wb') as f:
                    f.write(resp.read())
            print(f'  Downloaded {SECTORS_FILE.stat().st_size/1024/1024:.1f}MB')
        except Exception as e:
            print(f'  ❌ Download failed: {e}')
            print(f'  Manual download: {SECTORS_URL}')
            db.close()
            return
    
    print(f'\nLoading Brazil sector boundaries ({SECTORS_FILE.stat().st_size/1024/1024:.0f}MB)...')
    sectors_gdf = gpd.read_file(SECTORS_FILE)
    print(f'  {len(sectors_gdf):,} sectors, CRS: {sectors_gdf.crs}')
    print(f'  Columns: {list(sectors_gdf.columns[:8])}')
    
    # ═══ Spatial Join ════════════════════════════════════════════════
    print(f'\nSpatial joining {len(churches_df):,} churches → {len(sectors_gdf):,} sectors...')
    
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != sectors_gdf.crs:
        church_gdf = church_gdf.to_crs(sectors_gdf.crs)
    
    # Find sector ID column (varies by state shapefile version)
    id_cols = [c for c in sectors_gdf.columns if 'CD_SETOR' in c.upper()]
    name_cols = [c for c in sectors_gdf.columns if 'NM' in c.upper()]
    id_col = id_cols[0] if id_cols else sectors_gdf.columns[1]
    
    use_cols = [id_col, 'geometry']
    if name_cols:
        use_cols.insert(1, name_cols[0])
    
    joined = gpd.sjoin(
        church_gdf,
        sectors_gdf[use_cols],
        how='left',
        predicate='within'
    )
    matched = joined[id_col].notna().sum()
    print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    # ═══ Create church_census_BR ═════════════════════════════════════
    name_col = name_cols[0] if name_cols else None
    actual_id_col = id_col
    
    print(f'  Using sector ID column: {actual_id_col}')
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_census_BR (
            church_rowid    INTEGER PRIMARY KEY,
            setor_cod       TEXT,      -- CD_SETOR
            setor_name      TEXT,      -- Sector name if available
            source          TEXT DEFAULT 'ibge_setores_2022',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_cc_br_setor ON church_census_BR(setor_cod);
    ''')
    
    db.execute('DELETE FROM church_census_BR')
    
    cols = ['church_rowid', actual_id_col]
    if name_col and name_col in joined.columns:
        cols.append(name_col)
    
    result = joined[cols].dropna(subset=[actual_id_col]).copy()
    rows = []
    for r in result.itertuples():
        sid = str(getattr(r, actual_id_col))
        sname = str(getattr(r, name_col)) if name_col and name_col in joined.columns else None
        rows.append((int(r.church_rowid), sid, sname))
    
    db.executemany('INSERT INTO church_census_BR (church_rowid, setor_cod, setor_name) VALUES (?,?,?)', rows)
    db.commit()
    print(f'  Inserted {len(rows):,} rows')
    
    # ═══ Catalog ═════════════════════════════════════════════════════
    rc = db.execute("SELECT COUNT(*) FROM church_census_BR").fetchone()[0]
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', ('BR', 'church_census_BR', 'census', 'setor_censitario',
          'IBGE 2022 Census sectors per church', 3, rc))
    
    # ═══ Provenance ═════════════════════════════════════════════════
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'ibge_setores_2022',
        '_enrich_brazil.py',
        now, now, 0, len(rows),
        'setor_cod,setor_name',
        len(churches_df), matched,
        'completed',
        f'Brazil churches enriched: {matched}/{len(churches_df)} with census sectors'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print('DONE — Brazil churches tagged with IBGE census sectors')
    print(f'Table: church_census_BR ({rc:,} rows)')
    print(f'{"="*60}')


if __name__ == '__main__':
    main()

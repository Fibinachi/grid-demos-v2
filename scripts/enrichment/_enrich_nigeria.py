#!/usr/bin/env python3
"""
Nigeria Census + Election Spatial Join Pipeline

Downloads LGA boundaries from HDX, spatial joins churches,
creates church_census_NG table.

Nigeria: 774 LGAs, 37 states, 23K churches with GPS
Sources:
  - HDX: Nigeria Admin 0-2 boundaries (states + LGAs)
  - INEC/Kaggle: 2023 election results by LGA

Usage:
    python scripts/enrichment/_enrich_nigeria.py
"""
import sqlite3
import io
import os
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile

import geopandas as gpd
import pandas as pd
import urllib.request

DB = r'E:\grid\churches.db'
DATA_DIR = Path(r'E:\grid\data\nigeria_boundaries')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# HDX Nigeria Admin Boundaries — direct GeoJSON download
# Admin 0 = country, Admin 1 = state, Admin 2 = LGA
SHP_URL = "https://data.humdata.org/dataset/621d3f5d-1caa-416e-a39c-da80e82aa97b/resource/9e1c1c92-2bcd-4cc1-bb33-b464f7a6883b/download/nga_adm_osgof_20190417_SHP.zip"

# Primary: GADM 4.1 Nigeria (states + LGAs) — GeoPackage from UC Davis
GADM_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_NGA.gpkg"
# Fallback: geoBoundaries ADM2 (LGAs) — direct GeoJSON from GitHub
GEOBOUNDARIES_URL = "https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/gbOpen/NGA/ADM2/geoBoundaries-NGA-ADM2.geojson"


def main():
    db = sqlite3.connect(DB, timeout=120)
    
    # ═══ Load churches ═══════════════════════════════════════════════
    print('Loading Nigerian churches...')
    churches_df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude FROM churches WHERE country='NG' AND latitude IS NOT NULL",
        db
    )
    print(f'  {len(churches_df):,} NG churches with GPS')
    
    # ═══ Download boundaries ═════════════════════════════════════════
    # Try GADM GeoPackage first (UC Davis, reliable), then geoBoundaries GeoJSON
    gpkg_dest = DATA_DIR / "gadm41_NGA.gpkg"
    geojson_dest = DATA_DIR / "NGA_ADM2.geojson"
    
    bounds_file = None
    is_gpkg = False
    
    if not gpkg_dest.exists() and not geojson_dest.exists():
        print(f'\nDownloading Nigeria boundaries...')
        # Try GADM first
        try:
            print(f'  Trying GADM GeoPackage...')
            req = urllib.request.Request(GADM_URL, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=120) as resp:
                with open(gpkg_dest, 'wb') as f:
                    f.write(resp.read())
            print(f'  Downloaded {gpkg_dest.stat().st_size/1024/1024:.1f}MB (GADM)')
            bounds_file = gpkg_dest
            is_gpkg = True
        except Exception as e:
            print(f'  GADM failed: {e}')
            # Try geoBoundaries
            try:
                print(f'  Trying geoBoundaries GeoJSON...')
                req = urllib.request.Request(GEOBOUNDARIES_URL, headers={'User-Agent': 'GRID/1.0'})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    with open(geojson_dest, 'wb') as f:
                        f.write(resp.read())
                print(f'  Downloaded {geojson_dest.stat().st_size/1024/1024:.1f}MB (geoBoundaries)')
                bounds_file = geojson_dest
            except Exception as e2:
                print(f'  geoBoundaries also failed: {e2}')
                db.close()
                return
    else:
        # Use existing file
        if gpkg_dest.exists():
            bounds_file = gpkg_dest
            is_gpkg = True
        else:
            bounds_file = geojson_dest
    
    print(f'\nLoading boundaries ({bounds_file.stat().st_size/1024/1024:.0f}MB)...')
    gdf = gpd.read_file(bounds_file)
    
    # If GADM GeoPackage, select ADM2 (LGA) layer
    if is_gpkg and 'NAME_2' in gdf.columns:
        print(f'  Using GADM ADM2 (LGA) layer')
    elif is_gpkg:
        # Try to get ADM2 layer
        layers = gpd.list_layers(bounds_file) if hasattr(gpd, 'list_layers') else []
        print(f'  Layers: {layers}')
        # GADM usually has layers like 'gadm41_NGA' or 'ADM_ADM_2'
    
    print(f'  {len(gdf):,} features, CRS: {gdf.crs}')
    print(f'  Columns: {list(gdf.columns[:10])}')
    
    # ═══ Spatial Join ════════════════════════════════════════════════
    print(f'\nSpatial joining {len(churches_df):,} churches...')
    
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    if church_gdf.crs != gdf.crs:
        church_gdf = church_gdf.to_crs(gdf.crs)
    
    # Find useful columns
    name_cols = [c for c in gdf.columns if 'name' in c.lower() or 'shapeName' in c or 'admin' in c.lower()]
    id_cols = [c for c in gdf.columns if 'id' in c.lower() or 'code' in c.lower() or 'shapeID' in c]
    
    id_col = id_cols[0] if id_cols else gdf.columns[0]
    name_col = name_cols[0] if name_cols else (gdf.columns[1] if len(gdf.columns) > 1 else gdf.columns[0])
    
    use_cols = [id_col, name_col, 'geometry']
    
    joined = gpd.sjoin(
        church_gdf,
        gdf[use_cols],
        how='left',
        predicate='within'
    )
    matched = joined[id_col].notna().sum()
    print(f'  Matched: {matched:,} / {len(joined):,} ({100*matched/len(joined):.1f}%)')
    
    # ═══ Create church_census_NG ═════════════════════════════════════
    print(f'\nCreating church_census_NG...')
    print(f'  ID column: {id_col}')
    print(f'  Name column: {name_col}')
    
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_census_NG (
            church_rowid    INTEGER PRIMARY KEY,
            lga_code        TEXT,
            lga_name        TEXT,
            source          TEXT DEFAULT 'geoboundaries_nga_adm2',
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_cc_ng_lga ON church_census_NG(lga_code);
        CREATE INDEX IF NOT EXISTS idx_cc_ng_lga_name ON church_census_NG(lga_name);
    ''')
    
    db.execute('DELETE FROM church_census_NG')
    
    result = joined[['church_rowid', id_col, name_col]].dropna(subset=[id_col]).copy()
    rows = [(int(r.church_rowid), str(getattr(r, id_col)), str(getattr(r, name_col)))
            for r in result.itertuples()]
    
    db.executemany(
        'INSERT INTO church_census_NG (church_rowid, lga_code, lga_name) VALUES (?,?,?)',
        rows
    )
    db.commit()
    print(f'  Inserted {len(rows):,} rows')
    
    # ═══ State breakdown ══════════════════════════════════════════════
    # Check if there's a state column in the data
    state_col = next((c for c in gdf.columns if 'state' in c.lower() or 'admin1' in c.lower()), None)
    print('\n  Top LGAs by church count:')
    for r in db.execute('''
        SELECT lga_name, COUNT(*) as churches FROM church_census_NG
        GROUP BY lga_name ORDER BY churches DESC LIMIT 10
    ''').fetchall():
        print(f'    {r[0][:40]:40s}  {r[1]:,} churches')
    
    # ═══ Catalog ═════════════════════════════════════════════════════
    rc = db.execute("SELECT COUNT(*) FROM church_census_NG").fetchone()[0]
    db.execute('''
        INSERT OR REPLACE INTO church_census_catalog
            (country, table_name, category, geo_unit, description, variable_count, row_count, refresh_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, date('now'))
    ''', ('NG', 'church_census_NG', 'census', 'LGA',
          'Nigeria Local Government Areas per church', 3, rc))
    
    # ═══ Provenance ═════════════════════════════════════════════════
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'geoboundaries_nga_adm2',
        '_enrich_nigeria.py',
        now, now, 0, len(rows),
        'lga_code,lga_name',
        len(churches_df), matched,
        'completed',
        f'Nigeria LGA enrichment: {matched}/{len(churches_df)} churches'
    ))
    db.commit()
    db.close()
    
    print(f'\n{"="*60}')
    print('DONE — Nigeria churches tagged with LGA boundaries')
    print(f'Table: church_census_NG ({rc:,} rows)')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

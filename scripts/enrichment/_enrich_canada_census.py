#!/usr/bin/env python3
"""
Enrich Canadian churches with 2021 Census geography (DA + CT).

Creates church_census_ca table with:
  - church_rowid  -> churches.rowid (unique, FK)
  - dauid         -> Dissemination Area ID (finest census geography)
  - da_dguid      -> DA DGUID
  - ctuid         -> Census Tract ID (cartographic boundaries)
  - ct_dguid      -> CT DGUID
  - ct_name       -> CT name/number
  - province_code -> 2-digit PRUID

DA coverage: 79,085 / 79,556 (99.4%)
CT coverage: 52,013 / 79,556 (65.4% — cartographic boundaries, land only)
"""
import sqlite3
import os
import sys
from datetime import date

import geopandas as gpd
import pandas as pd

DB = r'E:\grid\churches.db'
DA_SHP = r'E:\grid\data\canada_census\lda_000b21a_e.shp'
CT_SHP = r'E:\grid\data\canada_census\lct_000b21a_e.shp'

# ── Step 1: Load churches (using rowid) ──────────────────────────────────
print('Loading Canadian churches from DB...')
db = sqlite3.connect(DB)
churches_df = pd.read_sql_query(
    "SELECT rowid, latitude, longitude FROM churches WHERE country='CA' AND latitude IS NOT NULL",
    db
)
print(f'  Loaded {len(churches_df):,} churches')
db.close()

# ── Step 2: DA Spatial Join ──────────────────────────────────────────────
print(f'\nLoading DA shapefile ({os.path.getsize(DA_SHP)/1024/1024:.0f} MB)...')
da_gdf = gpd.read_file(DA_SHP)
da_gdf = da_gdf.to_crs('EPSG:4326')
print(f'  DA polygons: {len(da_gdf):,}')

church_gdf = gpd.GeoDataFrame(
    {'church_rowid': churches_df['rowid'].values},
    geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
    crs='EPSG:4326'
)

print('  Running DA spatial join...')
da_joined = gpd.sjoin(
    church_gdf, da_gdf[['DAUID', 'DGUID', 'PRUID', 'geometry']],
    how='left', predicate='within'
)
da_matched = da_joined['DAUID'].notna().sum()
print(f'  DA matched: {da_matched:,} / {len(da_joined):,} ({100*da_matched/len(da_joined):.1f}%)')

da_result = da_joined[['church_rowid', 'DAUID', 'DGUID', 'PRUID']].copy()
da_result.columns = ['church_rowid', 'dauid', 'da_dguid', 'province_code']

# ── Step 3: CT Spatial Join ──────────────────────────────────────────────
print(f'\nLoading CT shapefile ({os.path.getsize(CT_SHP)/1024/1024:.0f} MB)...')
ct_gdf = gpd.read_file(CT_SHP)
ct_gdf = ct_gdf.to_crs('EPSG:4326')
print(f'  CT polygons: {len(ct_gdf):,}')

print('  Running CT spatial join...')
ct_joined = gpd.sjoin(
    church_gdf, ct_gdf[['CTUID', 'DGUID', 'CTNAME', 'PRUID', 'geometry']],
    how='left', predicate='within'
)
ct_matched = ct_joined['CTUID'].notna().sum()
print(f'  CT matched: {ct_matched:,} / {len(ct_joined):,} ({100*ct_matched/len(ct_joined):.1f}%)')

ct_result = ct_joined[['church_rowid', 'CTUID', 'DGUID', 'CTNAME', 'PRUID']].copy()
ct_result.columns = ['church_rowid', 'ctuid', 'ct_dguid', 'ct_name', 'ct_pruid']

# ── Step 4: Merge Results ────────────────────────────────────────────────
print('\nMerging DA + CT results...')
merged = da_result.merge(
    ct_result[['church_rowid', 'ctuid', 'ct_dguid', 'ct_name']],
    on='church_rowid', how='left'
)
print(f'  Merged: {len(merged):,} rows')
print(f'  With DAUID: {merged.dauid.notna().sum():,}')
print(f'  With CTUID: {merged.ctuid.notna().sum():,}')
print(f'  With both:  {(merged.dauid.notna() & merged.ctuid.notna()).sum():,}')

# ── Step 5: Create Table & Insert ────────────────────────────────────────
print('\nCreating church_census_ca table...')
db = sqlite3.connect(DB)

db.executescript('''
    CREATE TABLE IF NOT EXISTS church_census_ca (
        church_rowid    INTEGER PRIMARY KEY,
        dauid           TEXT,
        da_dguid        TEXT,
        ctuid           TEXT,
        ct_dguid        TEXT,
        ct_name         TEXT,
        province_code   TEXT,
        source_date     TEXT DEFAULT (date('now')),
        FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
    );
''')
print('  Table created (or already exists).')

# Clear and repopulate
print('  Clearing old data...')
db.execute('DELETE FROM church_census_ca')

print('  Inserting enrichment data...')
insert_sql = '''
    INSERT INTO church_census_ca
        (church_rowid, dauid, da_dguid, province_code, ctuid, ct_dguid, ct_name)
    VALUES (?, ?, ?, ?, ?, ?, ?)
'''
rows = list(merged.itertuples(index=False, name=None))
db.executemany(insert_sql, rows)
db.commit()
print(f'  Inserted {len(rows):,} rows')

# ── Step 6: Fix province_code type (cast to TEXT) ────────────────────────
# The PRUID from the shapefile is float; convert stored values
db.execute('''
    UPDATE church_census_ca
    SET province_code = CAST(CAST(province_code AS INTEGER) AS TEXT)
    WHERE province_code IS NOT NULL
''')
db.commit()
print('  Province codes cast to TEXT')

# ── Step 7: Provenance via provenance_log ────────────────────────────────
print('  Logging provenance...')
cur = db.execute('SELECT COUNT(*) FROM church_census_ca')
enriched_count = cur.fetchone()[0]

from datetime import datetime
now = datetime.now().isoformat()
db.execute('''
    INSERT INTO provenance_log
        (source, script_name, started_at, completed_at,
         churches_updated, churches_inserted, fields_populated,
         records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (
    'census_2021_ca',
    '_enrich_canada_census.py',
    now, now,
    0,              # churches_updated
    enriched_count, # churches_inserted
    'dauid,da_dguid,ctuid,ct_dguid,ct_name,province_code',
    79556,          # records_attempted
    da_matched,     # records_matched (DA is primary geography)
    'completed',
    f'DA: {da_matched:,}/{len(da_joined):,} ({100*da_matched/len(da_joined):.1f}%), '
    f'CT: {ct_matched:,}/{len(ct_joined):,} ({100*ct_matched/len(ct_joined):.1f}%)'
))
db.commit()
print('  Provenance logged')

db.close()
print('\n✓ Canadian census enrichment complete!')

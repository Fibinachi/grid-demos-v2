#!/usr/bin/env python3
"""
Enrich Canadian churches with Federal Electoral Districts (FEDs / Ridings).

Creates church_fed table with:
  - church_rowid  -> churches.rowid (FK)
  - fed_num       -> FED_NUM (5-digit, first 2 = province code)
  - fed_name_en   -> English name
  - fed_name_fr   -> French name
  - province_code -> 2-digit StatCan province code

FED boundaries: 2023 Representation Order (343 ridings)
Source: data/canada_boundaries/fed_2023/FED_CA_2023_EN.shp
"""
import sqlite3
import os
import sys
from datetime import datetime

import geopandas as gpd
import pandas as pd

DB = r'E:\grid\churches.db'
FED_SHP = r'E:\grid\data\canada_boundaries\fed_2023\FED_CA_2023_EN.shp'

# Province code mapping from FED_NUM prefix
PROVINCE_MAP = {
    '10': ('NL', 'Newfoundland and Labrador'),
    '11': ('PE', 'Prince Edward Island'),
    '12': ('NS', 'Nova Scotia'),
    '13': ('NB', 'New Brunswick'),
    '24': ('QC', 'Quebec'),
    '35': ('ON', 'Ontario'),
    '46': ('MB', 'Manitoba'),
    '47': ('SK', 'Saskatchewan'),
    '48': ('AB', 'Alberta'),
    '59': ('BC', 'British Columbia'),
    '60': ('YT', 'Yukon'),
    '61': ('NT', 'Northwest Territories'),
    '62': ('NU', 'Nunavut'),
}

def main():
    # ── Step 1: Load churches ──────────────────────────────────────────
    print('Loading Canadian churches from DB...')
    db = sqlite3.connect(DB)
    churches_df = pd.read_sql_query(
        "SELECT rowid, latitude, longitude FROM churches WHERE country='CA' AND latitude IS NOT NULL",
        db
    )
    print(f'  Loaded {len(churches_df):,} churches')

    # ── Step 2: Load FED shapefile ─────────────────────────────────────
    print(f'\nLoading FED shapefile ({os.path.getsize(FED_SHP)/1024/1024:.0f} MB)...')
    fed_gdf = gpd.read_file(FED_SHP)
    print(f'  Native CRS: {fed_gdf.crs}')
    fed_gdf = fed_gdf.to_crs('EPSG:4326')
    print(f'  FED polygons: {len(fed_gdf):,}')
    print(f'  Columns: {fed_gdf.columns.tolist()}')

    # Derive province codes from FED_NUM
    fed_gdf['province_code'] = fed_gdf['FED_NUM'].astype(str).str[:2]

    # ── Step 3: Spatial join ───────────────────────────────────────────
    church_gdf = gpd.GeoDataFrame(
        {'church_rowid': churches_df['rowid'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )

    print('\nRunning FED spatial join...')
    joined = gpd.sjoin(
        church_gdf,
        fed_gdf[['FED_NUM', 'ED_NAMEE', 'ED_NAMEF', 'province_code', 'geometry']],
        how='left',
        predicate='within'
    )
    matched = joined['FED_NUM'].notna().sum()
    total = len(joined)
    print(f'  Matched: {matched:,} / {total:,} ({100*matched/total:.1f}%)')

    # ── Step 4: Province breakdown ─────────────────────────────────────
    print('\n  By province:')
    prov_counts = joined[joined['FED_NUM'].notna()].groupby('province_code').size()
    for pc in sorted(prov_counts.index):
        pname = PROVINCE_MAP.get(pc, ('??', 'Unknown'))
        print(f'    {pc} ({pname[0]}): {prov_counts[pc]:,}')

    # ── Step 5: Unmatched analysis ─────────────────────────────────────
    unmatched = joined[joined['FED_NUM'].isna()]
    if len(unmatched) > 0:
        print(f'\n  Unmatched: {len(unmatched):,}')
        # Check if unmatched are in remote areas (coastal, northern)
        unmatched_ids = unmatched['church_rowid'].tolist()[:10]
        placeholders = ','.join('?' * len(unmatched_ids))
        samples = db.execute(
            f"SELECT name, city, state, latitude, longitude FROM churches WHERE rowid IN ({placeholders})",
            unmatched_ids
        ).fetchall()
        for s in samples:
            print(f'    {s[0][:50]} | {s[1]}, {s[2]} | ({s[3]:.3f}, {s[4]:.3f})')

    # ── Step 6: Create table ───────────────────────────────────────────
    print('\nCreating church_fed table...')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS church_fed (
            church_rowid    INTEGER PRIMARY KEY,
            fed_num         TEXT NOT NULL,
            fed_name_en     TEXT,
            fed_name_fr     TEXT,
            province_code   TEXT,
            source_date     TEXT DEFAULT (date('now')),
            FOREIGN KEY (church_rowid) REFERENCES churches(rowid)
        );
        CREATE INDEX IF NOT EXISTS idx_church_fed_num ON church_fed(fed_num);
        CREATE INDEX IF NOT EXISTS idx_church_fed_prov ON church_fed(province_code);
    ''')

    # Clear and repopulate
    db.execute('DELETE FROM church_fed')

    # Build result rows
    result = joined[['church_rowid', 'FED_NUM', 'ED_NAMEE', 'ED_NAMEF', 'province_code']].copy()
    result.columns = ['church_rowid', 'fed_num', 'fed_name_en', 'fed_name_fr', 'province_code']
    result = result.dropna(subset=['fed_num'])

    rows = [(int(r.church_rowid), str(int(r.fed_num)), r.fed_name_en, r.fed_name_fr, r.province_code)
            for r in result.itertuples()]
    db.executemany(
        'INSERT INTO church_fed (church_rowid, fed_num, fed_name_en, fed_name_fr, province_code) VALUES (?,?,?,?,?)',
        rows
    )
    db.commit()
    print(f'  Inserted {len(rows):,} rows')

    # ── Step 7: Verify ─────────────────────────────────────────────────
    cur = db.execute('''
        SELECT fed_num, fed_name_en, COUNT(*) as churches
        FROM church_fed
        GROUP BY fed_num
        ORDER BY churches DESC
        LIMIT 10
    ''')
    print('\n  Top 10 ridings by church count:')
    for r in cur.fetchall():
        print(f'    {r[0]} {r[1][:45]:45s}  {r[2]:,} churches')

    # ── Step 8: Provenance ─────────────────────────────────────────────
    now = datetime.now().isoformat()
    db.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        'elections_canada_fed',
        '_enrich_canada_fed.py',
        now, now,
        0, len(rows),
        'fed_num,fed_name_en,fed_name_fr,province_code',
        total, matched,
        'completed',
        f'FED spatial join: {matched}/{total} CA churches matched to {fed_gdf.FED_NUM.nunique()} ridings'
    ))
    db.commit()

    db.close()
    print(f'\n{"="*60}')
    print(f'DONE — {len(rows):,} churches tagged with federal electoral districts')
    print(f'Table: church_fed')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

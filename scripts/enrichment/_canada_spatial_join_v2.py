#!/usr/bin/env python3
"""
Spatial join: Canada 2021 Census geography onto Canadian church records.

1. Loads Canada Census Tract (CT) boundaries
2. Loads our Canadian churches with GPS coordinates
3. Does a point-in-polygon spatial join
4. Tags records with CTUID, CTNAME, PRUID
5. Adds Dissemination Area (DA) level if available
6. Writes results into the database
"""

import sqlite3
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import time
import sys

DB_PATH = r'E:\grid\churches.db'
CT_SHP = r'E:\grid\data\canada_census\lct_000b21a_e.shp'
DA_SHP = r'E:\grid\data\canada_census\lda_000b21a_e.shp'

# Province code to name/abbreviation
PR_PROVINCE = {
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

def load_churches(db):
    """Load Canadian church records with GPS coordinates."""
    print('Loading Canadian church records...')
    df = pd.read_sql_query("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE country = 'CA' AND latitude IS NOT NULL", db)
    print(f'  Loaded {len(df):,} records')
    return df

def do_spatial_join(churches_df, boundary_gdf, level_col, level_name):
    """Point-in-polygon spatial join, returns DataFrame with church_id + census columns."""
    print(f'\nSpatial join: churches -> {level_name}...')
    t0 = time.time()
    
    # Create points GeoDataFrame in WGS84
    church_gdf = gpd.GeoDataFrame(
        {'church_id': churches_df['id'].values},
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    # Reproject to match boundary CRS
    church_gdf = church_gdf.to_crs(boundary_gdf.crs)
    
    # Prepare boundary columns (exclude geometry)
    bcols = [c for c in boundary_gdf.columns if c != 'geometry']
    
    # Spatial join
    joined = gpd.sjoin(
        church_gdf,
        boundary_gdf[bcols + ['geometry']],
        how='left',
        predicate='within'
    )
    
    matched = joined[level_col].notna().sum()
    total = len(joined)
    print(f'  Matched: {matched:,} / {total:,} ({100*matched/total:.1f}%)')
    print(f'  Time: {time.time()-t0:.1f}s')
    
    return joined

def main():
    db = sqlite3.connect(DB_PATH)
    
    # Step 1: Load churches
    churches_df = load_churches(db)
    if len(churches_df) == 0:
        print('ERROR: No Canadian churches with coordinates found.')
        sys.exit(1)
    
    # Step 2: Load CT boundaries and join
    print(f'\nLoading Census Tract boundaries...')
    ct_gdf = gpd.read_file(CT_SHP)
    print(f'  {len(ct_gdf):,} CT polygons, CRS: {ct_gdf.crs}')
    
    ct_result = do_spatial_join(churches_df, ct_gdf, 'CTUID', 'Census Tract')
    ct_matched = ct_result[ct_result['CTUID'].notna()].copy()
    ct_unmatched = ct_result[ct_result['CTUID'].isna()].copy()
    
    print(f'\n=== CT Coverage ===')
    print(f'  Total: {len(ct_result):,}')
    print(f'  Matched: {len(ct_matched):,} ({100*len(ct_matched)/len(ct_result):.1f}%)')
    print(f'  Unmatched: {len(ct_unmatched):,}')
    
    # Province breakdown
    ct_matched['pruid'] = ct_matched['PRUID'].fillna('00')
    print(f'\n  By province (matched):')
    for pruid in sorted(ct_matched['PRUID'].unique()):
        if pd.isna(pruid): continue
        count = len(ct_matched[ct_matched['PRUID'] == pruid])
        prov = PR_PROVINCE.get(str(pruid), ('??', 'Unknown'))
        print(f'    {prov[0]} ({prov[1]}): {count:,}')
    
    # Step 3: Try DA if available
    da_result = None
    if os.path.exists(DA_SHP):
        print(f'\nLoading Dissemination Area boundaries...')
        da_gdf = gpd.read_file(DA_SHP)
        print(f'  {len(da_gdf):,} DA polygons, CRS: {da_gdf.crs}')
        da_result = do_spatial_join(churches_df, da_gdf, 'DAUID', 'Dissemination Area')
        da_matched = len(da_result[da_result['DAUID'].notna()])
        print(f'\n=== DA Coverage ===')
        print(f'  Matched: {da_matched:,} / {len(da_result):,} ({100*da_matched/len(da_result):.1f}%)')
    else:
        print(f'\nDA file not found ({DA_SHP}) - will add later')
    
    # Step 4: Save results to CSV
    out_dir = r'E:\grid\data\canada_census'
    os.makedirs(out_dir, exist_ok=True)
    
    ct_save = ct_result[['church_id', 'CTUID', 'DGUID', 'CTNAME', 'PRUID', 'LANDAREA']].copy()
    ct_save.columns = ['church_id', 'ctuid', 'ct_dguid', 'ct_name', 'ct_pruid', 'ct_landarea_km2']
    ct_save.to_csv(os.path.join(out_dir, 'church_ct_join.csv'), index=False)
    print(f'\nSaved CT join to church_ct_join.csv ({len(ct_save):,} rows)')
    print(f'  Matched: {ct_save["ctuid"].notna().sum():,}')
    
    if da_result is not None:
        da_save = da_result[['church_id', 'DAUID']].copy()
        da_save.columns = ['church_id', 'dauid']
        da_save.to_csv(os.path.join(out_dir, 'church_da_join.csv'), index=False)
        print(f'Saved DA join to church_da_join.csv ({len(da_save):,} rows)')
        print(f'  Matched: {da_save["dauid"].notna().sum():,}')
    
    # Step 5: Investigate unmatched
    print(f'\n=== Unmatched Analysis ===')
    unmatched_ids = ct_result[ct_result['CTUID'].isna()]['church_id'].dropna().unique()
    if len(unmatched_ids) > 0:
        id_list = list(unmatched_ids[:100])
        placeholders = ','.join(['?'] * len(id_list))
        cur = db.execute(f"SELECT source, COUNT(*) FROM churches WHERE id IN ({placeholders}) GROUP BY source ORDER BY COUNT(*) DESC", id_list)
        print(f'  Source breakdown (first 100 unmatched):')
        for r in cur.fetchall():
            print(f'    {r[0]}: {r[1]}')
    
    db.close()
    print(f'\n{"="*60}')
    print('DONE')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

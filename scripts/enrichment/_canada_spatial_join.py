#!/usr/bin/env python3
"""
Spatial join: Canada 2021 Census geography onto our ~79.5K Canadian church records.

Downloads census boundary files if not present, then:
1. Loads Canada Census Tract (CT) boundaries
2. Loads our Canadian churches with GPS coordinates
3. Does a point-in-polygon spatial join
4. Tags records with CTUID, CTNAME, PRUID (province)
5. Optionally does Dissemination Area (DA) level if available
6. Writes results into enrichment tables

Files used:
- CT boundaries: data/canada_census/lct_000b21a_e.shp
- DA boundaries: data/canada_census/lda_000b21a_e.shp
"""

import sqlite3
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import sys
import time

DB_PATH = r'E:\grid\churches.db'
CT_SHP = r'E:\grid\data\canada_census\lct_000b21a_e.shp'
DA_SHP = r'E:\grid\data\canada_census\lda_000b21a_e.shp'

# Province code mapping (PRUID → name/abbreviation)
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
    df = pd.read_sql_query(
        "SELECT id, name, city, state, country, latitude, longitude "
        "FROM churches WHERE country = 'CA' AND latitude IS NOT NULL",
        db
    )
    print(f'  Loaded {len(df):,} Canadian records with coordinates')
    return df

def load_census_boundaries(shp_path, level_name):
    """Load census boundary shapefile."""
    print(f'Loading {level_name} boundaries from {shp_path}...')
    if not os.path.exists(shp_path):
        print(f'  WARNING: File not found: {shp_path}')
        return None
    
    gdf = gpd.read_file(shp_path)
    print(f'  Loaded {len(gdf):,} {level_name} polygons')
    print(f'  Columns: {list(gdf.columns)}')
    print(f'  CRS: {gdf.crs}')
    return gdf

def do_spatial_join(churches_df, boundary_gdf, level_col, level_name):
    """Perform point-in-polygon spatial join."""
    print(f'\nSpatial joining churches to {level_name}...')
    t0 = time.time()
    
    # Create GeoDataFrame from church coordinates (WGS84)
    # Ensure id is a regular column, not just index
    churches_df = churches_df.copy()
    churches_df['_church_id'] = churches_df['id'].values
    
    church_gdf = gpd.GeoDataFrame(
        churches_df,
        geometry=gpd.points_from_xy(churches_df.longitude, churches_df.latitude),
        crs='EPSG:4326'
    )
    
    # Reproject church points to match boundary CRS (EPSG:3347 - Lambert Conformal Conic)
    church_gdf = church_gdf.to_crs(boundary_gdf.crs)
    print(f'  Reprojected churches to {boundary_gdf.crs}')
    
    # Spatial join (left join: keep all churches, add boundary attributes where found)
    join_cols = [c for c in boundary_gdf.columns if c not in ['geometry']]
    joined = gpd.sjoin(
        church_gdf,
        boundary_gdf[join_cols + ['geometry']],
        how='left',
        predicate='within'
    )
    
    # Count matches
    matched = joined[level_col].notna().sum()
    total = len(joined)
    print(f'  Matched: {matched:,} / {total:,} ({100*matched/total:.1f}%)')
    print(f'  Columns after join: {list(joined.columns)}')
    print(f'  Time: {time.time()-t0:.1f}s')
    
    return joined

def main():
    db = sqlite3.connect(DB_PATH)
    
    # Step 1: Load churches
    churches_df = load_churches(db)
    if len(churches_df) == 0:
        print('ERROR: No Canadian churches with coordinates found.')
        sys.exit(1)
    
    # Step 2: Load CT boundaries and do spatial join
    ct_gdf = load_census_boundaries(CT_SHP, 'Census Tract')
    
    results = {}
    
    if ct_gdf is not None:
        ct_joined = do_spatial_join(churches_df, ct_gdf, 'CTUID', 'Census Tract')
        results['ct'] = ct_joined
        
        # Summary
        print(f'\n=== CT Coverage Summary ===')
        matched = ct_joined['CTUID'].notna().sum()
        print(f'  Matched to CT: {matched:,} / {len(ct_joined):,} ({100*matched/len(ct_joined):.1f}%)')
        
        # By province
        ct_joined['pruid'] = ct_joined['PRUID'].fillna('00')
        print(f'\n  By province (matched only):')
        for pruid in sorted(ct_joined[ct_joined['PRUID'].notna()]['PRUID'].unique()):
            count = len(ct_joined[ct_joined['PRUID'] == pruid])
            prov = PR_PROVINCE.get(pruid, ('??', 'Unknown'))
            print(f'    {prov[0]} ({prov[1]}): {count:,}')
        
        # Unmatched
        unmatched = ct_joined[ct_joined['CTUID'].isna()]
        print(f'\n  Unmatched: {len(unmatched):,}')
        # Show some unmatched
        if len(unmatched) > 0:
            print(f'  Sample unmatched:')
            for _, row in unmatched.head(5).iterrows():
                print(f'    id={row["id"]} | {row["name"][:50]} | {row["city"]}, {row["state"]} | {row["latitude"]:.4f}, {row["longitude"]:.4f}')
    
    # Step 3: Try DA if available
    da_gdf = load_census_boundaries(DA_SHP, 'Dissemination Area')
    if da_gdf is not None:
        da_joined = do_spatial_join(churches_df, da_gdf, 'DAUID', 'Dissemination Area')
        results['da'] = da_joined
        
        matched = da_joined['DAUID'].notna().sum()
        print(f'\n=== DA Coverage ===')
        print(f'  Matched to DA: {matched:,} / {len(da_joined):,} ({100*matched/len(da_joined):.1f}%)')
    
    # Step 4: Report
    print(f'\n{"="*60}')
    print('RESULTS SUMMARY')
    print(f'{"="*60}')
    print(f'Total Canadian churches with GPS: {len(churches_df):,}')
    if 'ct' in results:
        ct_matched = results['ct']['CTUID'].notna().sum()
        print(f'Matched to Census Tract: {ct_matched:,} ({100*ct_matched/len(results["ct"]):.1f}%)')
    if 'da' in results:
        da_matched = results['da']['DAUID'].notna().sum()
        print(f'Matched to Dissemination Area: {da_matched:,} ({100*da_matched/len(results["da"]):.1f}%)')
    
    # Step 5: Store results (save to CSV for now, DB enrichment coming next)
    if 'ct' in results:
        ct_out = results['ct'][['_church_id', 'CTUID', 'DGUID', 'CTNAME', 'PRUID', 'LANDAREA']].copy()
        ct_out.columns = ['church_id', 'ctuid', 'ct_dguid', 'ct_name', 'ct_pruid', 'ct_landarea_km2']
        ct_out = ct_out.dropna(subset=['church_id'])
        out_path = r'E:\grid\data\canada_census\church_ct_join.csv'
        ct_out.to_csv(out_path, index=False)
        print(f'\nSaved CT join results to {out_path}')
        print(f'  Columns: {list(ct_out.columns)}')
        print(f'  Rows with CT: {ct_out["ctuid"].notna().sum():,}')
    
    db.close()
    print('\nDone.')

if __name__ == '__main__':
    main()

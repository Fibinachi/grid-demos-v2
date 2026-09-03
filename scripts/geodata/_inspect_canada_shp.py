#!/usr/bin/env python3
"""Inspect Canada census shapefiles."""
import geopandas as gpd

# CT shapefile
ct_path = r'E:\grid\data\canada_census\lct_000b21a_e.shp'
gdf = gpd.read_file(ct_path)
print('=== Census Tracts (CT) ===')
print(f'Columns: {list(gdf.columns)}')
print(f'Shape: {gdf.shape}')
print(f'CRS: {gdf.crs}')
print(f'Sample rows:')
print(gdf.head(3).to_string())
print(f'\nUnique provinces (PRUID): {sorted(gdf["PRUID"].unique())}')
print(f'Total CTs: {len(gdf)}')

# Check for DA file
import os
da_path = r'E:\grid\data\canada_census\lda_000b21a_e.shp'
if os.path.exists(da_path):
    dagdf = gpd.read_file(da_path)
    print('\n=== Dissemination Areas (DA) ===')
    print(f'Columns: {list(dagdf.columns)}')
    print(f'Shape: {dagdf.shape}')
    print(f'CRS: {dagdf.crs}')
    print(f'Total DAs: {len(dagdf)}')
else:
    print(f'\nDA file not yet downloaded ({da_path})')

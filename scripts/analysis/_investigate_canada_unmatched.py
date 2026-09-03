#!/usr/bin/env python3
"""Investigate why 27.5K Canadian records don't match census tracts."""
import sqlite3
import pandas as pd
import geopandas as gpd
import os

DB_PATH = r'E:\grid\churches.db'

db = sqlite3.connect(DB_PATH)

# Load join results
df = pd.read_csv(r'E:\grid\data\canada_census\church_ct_join.csv')
unmatched = df[df['ctuid'].isna()].copy()
print(f'Unmatched records: {len(unmatched):,}')

# Get full details from DB
ids = unmatched['church_id'].tolist()
if ids:
    # Chunk to avoid SQLite limit
    chunks = [ids[i:i+900] for i in range(0, min(len(ids), 5000), 900)]
    all_rows = []
    for chunk in chunks:
        placeholders = ','.join(['?'] * len(chunk))
        cur = db.execute(f"SELECT id, name, city, state, source, latitude, longitude, faith FROM churches WHERE id IN ({placeholders})", chunk)
        all_rows.extend(cur.fetchall())
    
    details = pd.DataFrame(all_rows, columns=['id','name','city','state','source','lat','lon','faith'])
    print(f'\n=== Unmatched details ({len(details)} records) ===')
    print(f'By source:')
    print(details['source'].value_counts().head(20).to_string())
    print(f'\nBy province:')
    print(details['state'].value_counts().head(20).to_string())
    print(f'\nBy faith:')
    print(details['faith'].value_counts().head(20).to_string())
    
    # Check for northern territories
    northern = details[details['state'].isin(['YT','NT','NU',''])]
    print(f'\nNorthern territories (YT/NT/NU/None): {len(northern)}')
    
    # Check for US-border proximity (unmatched may have wrong country code)
    us_border = details[(details['lat'] > 41) & (details['lat'] < 50) & (details['lon'] < -60) & (details['lon'] > -130)]
    print(f'US border region: {len(us_border)}')
    
    # Check for maritime / coastal (cartographic file may not include islands)
    coastal = details[details['state'] == 'NL']
    print(f'Newfoundland: {len(coastal)}')
    
    # Check lat/lon extremes
    print(f'\nLat range: {details["lat"].min():.2f} to {details["lat"].max():.2f}')
    print(f'Lon range: {details["lon"].min():.2f} to {details["lon"].max():.2f}')
    
    # Look at some specific unmatched entries
    print(f'\n=== Sample unmatched (10) ===')
    for _, row in details.head(10).iterrows():
        print(f'  id={row["id"]} | {str(row["name"])[:60]} | {row["city"]}, {row["state"]} | {row["lat"]:.4f}, {row["lon"]:.4f} | faith={row["faith"]}')

db.close()

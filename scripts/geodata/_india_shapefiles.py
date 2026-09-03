"""
Download India shapefiles and create faith group overlay maps.
Uses GADM administrative boundaries (Level 1 = states/UTs).
"""
import os
import sqlite3
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

DATA_DIR = Path('data/shapefiles')
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Step 1: Download India state boundaries from GADM ──────────────────────
states_path = DATA_DIR / 'india_states_gadm41.gpkg'
india_path = DATA_DIR / 'india_country_gadm41.gpkg'
gadm_url = 'https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_IND.gpkg'

if not states_path.exists():
    print("Downloading India state boundaries from GADM...")
    india_states = gpd.read_file(gadm_url, layer='ADM_ADM_1')
    india_states.to_file(states_path, driver='GPKG')
    print(f"States saved to {states_path}")
else:
    print(f"Loading cached states: {states_path}")

india = gpd.read_file(states_path)

print(f"India admin boundaries: {len(india)} features (Level 1 = States/UTs)")
print(f"Columns: {list(india.columns)}")
print(f"CRS: {india.crs}")

# ── Step 2: Load churches data for India ────────────────────────────────────
conn = sqlite3.connect('churches.db', timeout=30)
query = """
    SELECT id, name, denomination, faith, faith_tradition, 
           latitude, longitude, state, city
    FROM churches 
    WHERE country = 'IN' AND latitude IS NOT NULL
"""
df = pd.read_sql_query(query, conn)
conn.close()
print(f"\nChurches in India: {len(df):,}")

# Map faith to display groups
faith_colors = {
    'Hindu':     '#FF9933',  # saffron
    'Christian': '#3366CC',  # blue
    'Islam':     '#33AA33',  # green
    'Sikh':      '#FFD700',  # gold
    'Buddhist':  '#CC3333',  # red
    'Jewish':    '#9933CC',  # purple
}
# Assign color based on faith
df['faith_group'] = df['faith'].fillna('Unknown')
df['color'] = df['faith_group'].map(faith_colors).fillna('#888888')

faith_counts = df['faith_group'].value_counts()
print("\nFaith groups:")
for f, cnt in faith_counts.items():
    print(f"  {f}: {cnt:,}")

# ── Step 3: Create the map ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(24, 14))

# ---- Map 1: Faith group points on state boundaries ----
ax1 = axes[0]
# Plot India state boundaries
india.boundary.plot(ax=ax1, color='#333333', linewidth=0.5)

# Plot points by faith group (sample if too many to avoid overplotting)
sample_n = min(50000, len(df))
if len(df) > sample_n:
    df_plot = df.sample(sample_n, random_state=42)
    ax1.set_title(f'India Faith Groups ({sample_n:,} of {len(df):,} points sampled)', fontsize=14)
else:
    df_plot = df
    ax1.set_title(f'India Faith Groups ({len(df):,} points)', fontsize=14)

for faith, color in faith_colors.items():
    subset = df_plot[df_plot['faith_group'] == faith]
    if len(subset) > 0:
        ax1.scatter(subset['longitude'], subset['latitude'], 
                     c=color, s=1, alpha=0.4, label=f'{faith} ({faith_counts.get(faith, 0):,})')

ax1.legend(loc='lower right', markerscale=8, fontsize=9, framealpha=0.8)
ax1.set_xlabel('Longitude')
ax1.set_ylabel('Latitude')
ax1.set_aspect('equal')

# ---- Map 2: Faith majority by state (spatial join) ----
ax2 = axes[1]

# Spatial join: assign each church to its state
churches_gdf = gpd.GeoDataFrame(
    df[['faith_group', 'latitude', 'longitude']],
    geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs='EPSG:4326'
)

# Use GID_1 level (states)
states = india[['GID_1', 'NAME_1', 'geometry']].copy()

# Spatial join
joined = gpd.sjoin(churches_gdf, states, how='inner', predicate='within')

# Count faith groups per state
state_faith = joined.groupby(['NAME_1', 'faith_group']).size().unstack(fill_value=0)

# Find majority faith per state
state_faith['total'] = state_faith.sum(axis=1)
state_faith['majority'] = state_faith.drop(columns='total').idxmax(axis=1)
state_faith['majority_pct'] = state_faith.drop(columns=['total', 'majority']).max(axis=1) / state_faith['total'] * 100

print("\nFaith majority by state:")
for state_name, row in state_faith.iterrows():
    print(f"  {state_name}: {row['majority']} ({row['majority_pct']:.1f}%)")

# Color states by majority faith
states = states.merge(state_faith[['majority']], left_on='NAME_1', right_index=True, how='left')
states['majority'] = states['majority'].fillna('No data')

state_colors = {**faith_colors, 'No data': '#DDDDDD'}
states['color'] = states['majority'].map(state_colors)

states.plot(ax=ax2, color=states['color'], edgecolor='#333333', linewidth=0.5)

# Add legend
from matplotlib.patches import Patch
legend_elements = [Patch(facecolor=color, edgecolor='#333', label=f'{faith} majority')
                   for faith, color in faith_colors.items()]
legend_elements.append(Patch(facecolor='#DDDDDD', edgecolor='#333', label='No data'))
ax2.legend(handles=legend_elements, loc='lower right', fontsize=9, framealpha=0.8)
ax2.set_title('Majority Faith Group by State/UT', fontsize=14)
ax2.set_aspect('equal')
ax2.axis('off')

# ---- Final layout ----
fig.suptitle('India: Religious Demographics vs Administrative Boundaries', 
             fontsize=18, fontweight='bold', y=0.98)
plt.tight_layout()

out_path = DATA_DIR / 'india_faith_map.png'
fig.savefig(out_path, dpi=150, bbox_inches='tight', facecolor='white')
print(f"\nMap saved to: {out_path}")

# Also save the state-level summary as CSV
state_faith.to_csv(DATA_DIR / 'india_state_faith_summary.csv')
print(f"State summary saved to: {DATA_DIR}/india_state_faith_summary.csv")

# Also export state boundaries with faith data as GeoJSON for external use
states_out = states[['NAME_1', 'majority', 'geometry']].copy()
geojson_path = DATA_DIR / 'india_states_faith.geojson'
states_out.to_file(geojson_path, driver='GeoJSON')
print(f"GeoJSON saved to: {geojson_path}")

plt.show()
print("\nDone!")

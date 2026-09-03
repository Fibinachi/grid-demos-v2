"""
Generate interactive Plotly map: churches in flood zones by tract elevation.
Uses outputs/flood_elevation_map.json from compute_elevation_diffs.py.
"""
import json, plotly.express as px, plotly.graph_objects as go
import pandas as pd

print("Loading map data...")
with open('outputs/flood_elevation_map.json') as f:
    data = json.load(f)

df = pd.DataFrame(data)
print(f"Loaded {len(df):,} churches")

# Sample for performance (keep all high-risk, sample lower-risk)
high_risk = df[df['inland_flood'] > 80]
moderate = df[(df['inland_flood'] > 50) & (df['inland_flood'] <= 80)]
sample_mod = moderate.sample(n=min(len(moderate), 20000), random_state=42)
plot_df = pd.concat([high_risk, sample_mod])
print(f"Plotting {len(plot_df):,} points ({len(high_risk):,} high-risk + {len(sample_mod):,} sample)")

# Clamp negative elevations for marker size
plot_df['tract_el_abs'] = plot_df['tract_el'].clip(lower=1)

fig = px.scatter_mapbox(
    plot_df,
    lat='lat',
    lon='lon',
    color='risk_score',
    size='tract_el_abs',
    size_max=8,
    color_continuous_scale='RdYlGn_r',
    hover_name='name',
    hover_data={
        'tract_el': ':.0f',
        'inland_flood': ':.0f',
        'risk_score': ':.1f',
        'risk_rating': True,
        'state': True,
        'county': True,
        'lat': False,
        'lon': False
    },
    title='US Churches in Flood Zones — Tract Elevation vs FEMA Risk<br><sup>Size = elevation | Color = risk score (red=high)</sup>',
    zoom=3,
    center={'lat': 39.8, 'lon': -98.5},
    height=800,
    mapbox_style='carto-positron'
)

fig.write_html('outputs/flood_elevation_map.html')
print("Saved outputs/flood_elevation_map.html")

# ── Second map: top high-ground churches in flood zones ──
print("\nGenerating high-ground heatmap...")
# For churches WITH church elevations, compute height above tract
# Since we have church_elevation still being fetched, use tract elevation as proxy for now
# Rank by tract elevation percentile within each flood risk level

# Get the top 500 highest-tract-elevation churches in high flood zones
top_churches = high_risk.nlargest(500, 'tract_el')
top_churches['flood_abs'] = top_churches['inland_flood'].clip(lower=1)

fig2 = px.scatter_mapbox(
    top_churches,
    lat='lat',
    lon='lon',
    color='tract_el',
    size='flood_abs',
    size_max=12,
    color_continuous_scale='Viridis',
    hover_name='name',
    hover_data={
        'tract_el': ':.0f',
        'inland_flood': ':.0f',
        'risk_score': ':.1f',
        'state': True,
        'county': True,
        'lat': False,
        'lon': False
    },
    title='Top 500 Highest-Ground Churches in Flood Zones<br><sup>Color = tract elevation | Size = flood risk</sup>',
    zoom=3,
    center={'lat': 39.8, 'lon': -98.5},
    height=800,
    mapbox_style='carto-positron'
)

fig2.write_html('outputs/flood_high_ground_map.html')
print("Saved outputs/flood_high_ground_map.html")

# ── Summary stats ──
print(f"\n=== SUMMARY ===")
print(f"Total churches in map: {len(df):,}")
print(f"  High flood risk (IFLD>80): {len(high_risk):,}")
print(f"  Moderate flood risk (IFLD 50-80): {len(moderate):,}")
print(f"  Tract elevation range: {df['tract_el'].min():.0f}m - {df['tract_el'].max():.0f}m")
print(f"  Risk score range: {df['risk_score'].min():.1f} - {df['risk_score'].max():.1f}")

# Top 10 highest-ground churches in worst flood zones
worst = high_risk.nlargest(10, 'tract_el')
print(f"\nTop 10 highest-ground churches in high flood zones:")
for _, r in worst.iterrows():
    name = str(r.get('name', ''))[:50]
    state = str(r.get('state', ''))[:4]
    county = str(r.get('county', ''))[:15]
    print(f"  {name:50s} {county:15s} {state:4s} {r['tract_el']:6.0f}m  flood={r['inland_flood']:.0f}")

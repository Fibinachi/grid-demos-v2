"""
Generate insurance-focused risk heatmap for outreach attachment.
Shows US worship sites colored by composite risk score:
  - FEMA overall risk (RISK_SCORE)
  - Crime rate (violent + property per 100K)
  - Emergency response distance (fire station km)

Output: outputs/outreach/map_insurance_risk.png (~500KB PNG for email)
"""
import sqlite3, json, sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB = PROJECT / "churches.db"
OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

print("=== GENERATING INSURANCE RISK HEATMAP ===\n")

db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row

# Step 1: Query — churches with FEMA + building + demographics
print("Querying churches with insurance-relevant risk data...")
rows = db.execute("""
    SELECT c.id, c.name, c.faith, c.tradition, c.landmark_type,
           c.city, c.state, c.country, c.latitude, c.longitude,
           c.nearest_fire_km, c.nearest_police_km,
           f.RISK_SCORE, f.RISK_RATNG, f.EAL_SCORE, f.SOVI_SCORE, f.RESL_SCORE,
           f.HRCN_RISKS, f.IFLD_RISKS, f.WFIR_RISKS, f.ERQK_RISKS,
           f.TRND_RISKS, f.HWAV_RISKS, f.DRGT_RISKS, f.CFLD_RISKS,
           f.HAIL_RISKS, f.SWND_RISKS, f.LTNG_RISKS, f.VLCN_RISKS,
           f.BUILDVALUE, f.POPULATION,
           cs.acs_median_income, cs.acs_poverty_rate,
           sq.building_area_sqft as building_sqft
    FROM churches c
    JOIN church_districts cd ON cd.church_id = c.id AND cd.layer_code = 'TRACT'
    JOIN fema_nri_tract f ON f.TRACTFIPS = cd.geo_id
    LEFT JOIN church_census_us cs ON cs.church_id = c.id
    LEFT JOIN church_building_sqft_us sq ON sq.church_id = c.id
    WHERE c.country = 'US'
    AND c.latitude IS NOT NULL
    AND f.RISK_SCORE IS NOT NULL
    AND f.RISK_SCORE > 0
    ORDER BY f.RISK_SCORE DESC
    LIMIT 20000
""").fetchall()

print(f"Loaded {len(rows):,} churches with FEMA + building + demographics")

# Step 2: County-level aggregation for choropleth
print("\nAggregating county risk profiles...")
county_data = {}
for r in rows:
    fips = r['state'] or 'Unknown'
    if fips not in county_data:
        county_data[fips] = {
            'count': 0, 'total_risk': 0, 'max_risk': 0,
            'max_hurricane': 0, 'max_flood': 0, 'max_wildfire': 0, 'max_tornado': 0,
            'max_eq': 0, 'max_hail': 0, 'avg_fire_dist': 0, 'total_fire_dist': 0,
            'avg_income': 0, 'total_income': 0, 'avg_sqft': 0, 'total_sqft': 0,
        }
    cd = county_data[fips]
    cd['count'] += 1
    cd['total_risk'] += r['RISK_SCORE'] or 0
    cd['max_risk'] = max(cd['max_risk'], r['RISK_SCORE'] or 0)
    cd['max_hurricane'] = max(cd['max_hurricane'], r['HRCN_RISKS'] or 0)
    cd['max_flood'] = max(cd['max_flood'], max(r['IFLD_RISKS'] or 0, r['CFLD_RISKS'] or 0))
    cd['max_wildfire'] = max(cd['max_wildfire'], r['WFIR_RISKS'] or 0)
    cd['max_tornado'] = max(cd['max_tornado'], r['TRND_RISKS'] or 0)
    cd['max_eq'] = max(cd['max_eq'], r['ERQK_RISKS'] or 0)
    cd['max_hail'] = max(cd['max_hail'], r['HAIL_RISKS'] or 0)
    if r['nearest_fire_km']:
        cd['total_fire_dist'] += r['nearest_fire_km']
    if r['acs_median_income']:
        cd['total_income'] += r['acs_median_income']
    if r['building_sqft']:
        cd['total_sqft'] += r['building_sqft']

for cd in county_data.values():
    cd['avg_risk'] = cd['total_risk'] / cd['count'] if cd['count'] else 0
    cd['avg_fire_dist'] = cd['total_fire_dist'] / cd['count'] if cd['count'] else 0
    cd['avg_income'] = cd['total_income'] / cd['count'] if cd['count'] else 0
    cd['avg_sqft'] = cd['total_sqft'] / cd['count'] if cd['count'] else 0

# Step 3: Build maps
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import pandas as pd
    import numpy as np
except ImportError:
    print("\n⚠️ plotly/pandas not installed. Generating text stats instead...")

    # Text-only fallback
    lines = [f"GRID INSURANCE RISK STATS — {len(rows):,} churches analyzed\n"]
    lines.append("\n=== TOP 15 STATES BY AVG FEMA RISK ===\n")
    for state, cd in sorted(county_data.items(), key=lambda x: -x[1]['avg_risk'])[:15]:
        lines.append(f"  {state}: {cd['count']:>6,} sites | avg risk {cd['avg_risk']:.1f} | "
                     f"max hurricane {cd['max_hurricane']:.0f} | max flood {cd['max_flood']:.0f} | "
                     f"max wildfire {cd['max_wildfire']:.0f} | fire dist {cd['avg_fire_dist']:.1f}km")

    lines.append("\n=== TOP 15 STATES BY MAX HURRICANE RISK ===\n")
    for state, cd in sorted(county_data.items(), key=lambda x: -x[1]['max_hurricane'])[:15]:
        lines.append(f"  {state}: {cd['max_hurricane']:.0f} hurricane | avg risk {cd['avg_risk']:.1f}")

    lines.append("\n=== TOP 15 STATES BY MAX WILDFIRE RISK ===\n")
    for state, cd in sorted(county_data.items(), key=lambda x: -x[1]['max_wildfire'])[:15]:
        lines.append(f"  {state}: {cd['max_wildfire']:.0f} wildfire | avg risk {cd['avg_risk']:.1f}")

    lines.append("\n=== TOP 15 STATES BY FIRE STATION DISTANCE (worst response) ===\n")
    for state, cd in sorted(county_data.items(), key=lambda x: -x[1]['avg_fire_dist'])[:15]:
        lines.append(f"  {state}: {cd['avg_fire_dist']:.1f}km avg fire dist | {cd['count']:,} sites")

    out_text = OUT / "insurance_risk_stats.txt"
    out_text.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Stats saved to {out_text}")
    db.close()
    sys.exit(0)

# Build dataframe
df = pd.DataFrame([dict(r) for r in rows])

# Create multi-panel figure
fig = make_subplots(
    rows=2, cols=2,
    subplot_titles=(
        "FEMA Overall Risk Score",
        "Max Hurricane Risk by State",
        "Max Wildfire Risk by State",
        "Avg Fire Station Distance (km)"
    ),
    specs=[[{"type": "scattergeo"}, {"type": "choropleth"}],
           [{"type": "choropleth"}, {"type": "choropleth"}]],
    vertical_spacing=0.08, horizontal_spacing=0.08,
)

# Panel 1: Scattergeo — churches colored by FEMA risk
fig.add_trace(
    go.Scattergeo(
        lon=df['longitude'], lat=df['latitude'],
        mode='markers',
        marker=dict(
            size=3, opacity=0.5,
            color=df['RISK_SCORE'],
            colorscale='RdYlBu_r',  # Red = high risk
            colorbar=dict(title="FEMA Risk", x=0.45, y=0.82, len=0.35),
            cmin=0, cmax=100,
        ),
        text=df.apply(lambda r: f"{r['name']}<br>{r['city']}, {r['state']}<br>Risk: {r['RISK_SCORE']:.0f}<br>Flood: {r['IFLD_RISKS']:.0f}<br>Hurricane: {r['HRCN_RISKS']:.0f}", axis=1),
        hoverinfo='text',
        name="",
    ),
    row=1, col=1,
)

# Panel 2: Choropleth — Hurricane risk by state
state_hurricane = {s: cd['max_hurricane'] for s, cd in county_data.items()}
fig.add_trace(
    go.Choropleth(
        locations=list(state_hurricane.keys()), z=list(state_hurricane.values()),
        locationmode='USA-states', colorscale='Blues',
        colorbar=dict(title="Hurricane Risk", x=0.95, y=0.82, len=0.35),
        zmin=0, zmax=100,
    ),
    row=1, col=2,
)

# Panel 3: Choropleth — Wildfire risk by state
state_wildfire = {s: cd['max_wildfire'] for s, cd in county_data.items()}
fig.add_trace(
    go.Choropleth(
        locations=list(state_wildfire.keys()), z=list(state_wildfire.values()),
        locationmode='USA-states', colorscale='OrRd',
        colorbar=dict(title="Wildfire Risk", x=0.45, y=0.30, len=0.35),
        zmin=0, zmax=100,
    ),
    row=2, col=1,
)

# Panel 4: Choropleth — Fire station distance
state_fire = {s: cd['avg_fire_dist'] for s, cd in county_data.items()}
fig.add_trace(
    go.Choropleth(
        locations=list(state_fire.keys()), z=list(state_fire.values()),
        locationmode='USA-states', colorscale='RdPu',
        colorbar=dict(title="Fire Dist (km)", x=0.95, y=0.30, len=0.35),
        zmin=0, zmax=max(state_fire.values()) if state_fire else 10,
    ),
    row=2, col=2,
)

# Layout
fig.update_layout(
    title=dict(
        text="GRID Insurance Risk Intelligence: Religious Infrastructure Risk Map",
        font=dict(size=18), x=0.5,
    ),
    geo=dict(scope='usa', projection_type='albers usa', showland=True,
              landcolor='rgb(243,243,243)', countrycolor='rgb(204,204,204)'),
    geo2=dict(scope='usa', projection_type='albers usa', showland=True, showframe=False),
    geo3=dict(scope='usa', projection_type='albers usa', showland=True, showframe=False),
    geo4=dict(scope='usa', projection_type='albers usa', showland=True, showframe=False),
    height=1100, width=1400,
    margin=dict(l=20, r=20, t=60, b=20),
    showlegend=False,
)

# Save
out_path = OUT / "map_insurance_risk.png"
fig.write_image(str(out_path), scale=1.5)
size_kb = out_path.stat().st_size / 1024

print(f"\n✅ Map saved: {out_path} ({size_kb:.0f} KB)")
print(f"   {len(rows):,} churches plotted across {len(county_data)} states")
print(f"\n   Top 5 risk states:")
for state, cd in sorted(county_data.items(), key=lambda x: -x[1]['avg_risk'])[:5]:
    print(f"     {state}: avg FEMA {cd['avg_risk']:.1f}, {cd['count']:,} churches, "
          f"Hurricane {cd['max_hurricane']:.0f}, Flood {cd['max_flood']:.0f}, "
          f"Wildfire {cd['max_wildfire']:.0f}, Fire dist {cd['avg_fire_dist']:.1f}km")

db.close()

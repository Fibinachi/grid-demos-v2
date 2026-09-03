"""
Generate humanitarian-focused disaster risk map for outreach attachment.
Shows US worship sites colored by FEMA overall risk score +
county-level risk aggregation.

Output: outputs/outreach/map_us_disaster_risk.png (~500KB PNG for email)
"""
import sqlite3, json
from pathlib import Path
from collections import Counter

DB = Path("churches.db")

print("=== GENERATING DISASTER RISK MAP ===\n")

# Step 1: Query — churches with FEMA risk scores
print("Querying churches with FEMA risk scores...")
db = sqlite3.connect(str(DB))
db.row_factory = sqlite3.Row

# Get a representative sample: one church per county with risk > 0
rows = db.execute("""
    SELECT c.id, c.name, c.faith, c.tradition, c.landmark_type,
           c.city, c.state, c.country, c.latitude, c.longitude,
           f.RISK_SCORE, f.RISK_RATNG, f.EAL_SCORE, f.SOVI_SCORE, f.RESL_SCORE,
           f.HRCN_RISKS, f.IFLD_RISKS, f.WFIR_RISKS, f.ERQK_RISKS,
           f.TRND_RISKS, f.HWAV_RISKS, f.DRGT_RISKS, f.CFLD_RISKS
    FROM churches c
    JOIN church_districts d ON d.church_id = c.id AND d.layer_code = 'TRACT'
    JOIN fema_nri_tract f ON f.TRACTFIPS = d.geo_id
    WHERE c.country = 'US'
    AND c.latitude IS NOT NULL
    AND f.RISK_SCORE IS NOT NULL
    AND f.RISK_SCORE > 0
    ORDER BY f.RISK_SCORE DESC
    LIMIT 15000
""").fetchall()

print(f"Loaded {len(rows):,} churches with FEMA risk scores")

# Step 2: State-level aggregation (use state field consistently)
county_risk = {}
for r in rows:
    key = (r['state'] or "Unknown").strip()
    if key not in county_risk:
        county_risk[key] = {'count': 0, 'total_risk': 0, 'max_risk': 0, 'max_hurricane': 0, 'max_flood': 0, 'max_wildfire': 0}
    county_risk[key]['count'] += 1
    county_risk[key]['total_risk'] += r['RISK_SCORE'] or 0
    county_risk[key]['max_risk'] = max(county_risk[key]['max_risk'], r['RISK_SCORE'] or 0)
    county_risk[key]['max_hurricane'] = max(county_risk[key]['max_hurricane'], r['HRCN_RISKS'] or 0)
    county_risk[key]['max_flood'] = max(county_risk[key]['max_flood'], r['IFLD_RISKS'] or 0)
    county_risk[key]['max_wildfire'] = max(county_risk[key]['max_wildfire'], r['WFIR_RISKS'] or 0)

# Step 3: Build Plotly map
try:
    import plotly.express as px
    import plotly.graph_objects as go
    import pandas as pd
    import numpy as np
except ImportError:
    print("plotly not installed. Install with: pip install plotly pandas")
    print("Generating fallback static stats instead...")
    # Fallback: output text stats
    out_text = Path("outputs/outreach/humanitarian_stats.txt")
    lines = [f"GRID DISASTER RISK STATS — {len(rows):,} churches with FEMA scores\n"]
    lines.append(f"States with most high-risk churches:")
    for state, data in sorted(county_risk.items(), key=lambda x: -x[1]['avg_risk'] * x[1]['count'])[:15]:
        avg = data['total_risk'] / max(data['count'], 1)
        lines.append(f"  {state}: {data['count']:,} churches, avg risk {avg:.1f}, max {data['max_risk']:.1f}")
    out_text.write_text('\n'.join(lines))
    print(f"Stats saved to {out_text}")
    db.close()
    import sys; sys.exit(0)

df = pd.DataFrame([dict(r) for r in rows])

# Risk color scale
risk_colors = {
    'Very Low': '#2ecc71', 'Low': '#27ae60',
    'Relatively Moderate': '#f1c40f', 'Moderate': '#f39c12',
    'Relatively High': '#e67e22', 'High': '#e74c3c',
    'Very High': '#c0392b'
}

# Create main scatter map
fig = go.Figure()

# Add churches as scatter points, colored by risk score
risk_scores = df['RISK_SCORE'].fillna(0)
# Use log scale for better visibility
size = np.clip(risk_scores / risk_scores.max() * 12, 2, 12)

fig.add_trace(go.Scattergeo(
    lon=df['longitude'],
    lat=df['latitude'],
    mode='markers',
    marker=dict(
        size=size,
        color=risk_scores,
        colorscale='RdYlGn_r',
        colorbar=dict(
            title=dict(text='FEMA Risk Score', side='right'),
            thickness=15,
            len=0.6
        ),
        cmin=0,
        cmax=100,
        opacity=0.5,
        line=dict(width=0.1, color='white')
    ),
    text=[f"{n}<br>{c}, {s}<br>Risk: {r:.1f} ({rt})<br>Hurricane: {h} | Flood: {f} | Wildfire: {w}"
          for n, c, s, r, rt, h, f, w in zip(
              df['name'], df['city'], df['state'],
              df['RISK_SCORE'], df['RISK_RATNG'],
              df['HRCN_RISKS'], df['IFLD_RISKS'], df['WFIR_RISKS'])],
    hoverinfo='text',
    name='Worship Sites'
))

# Update layout
fig.update_layout(
    title=dict(
        text='<b>GRID: Worship Sites by FEMA National Risk Index Score</b><br>'
             '<sub>3.5M worship sites globally — pre-positioned community hubs for disaster response</sub>',
        x=0.5, xanchor='center'
    ),
    geo=dict(
        scope='usa',
        projection_type='albers usa',
        showland=True,
        landcolor='#f5f5f5',
        coastlinecolor='#888',
        countrycolor='#888',
        showlakes=True,
        lakecolor='#e3f2fd',
        subunitcolor='#ccc',
        bgcolor='white'
    ),
    margin=dict(l=0, r=0, t=80, b=0),
    height=650,
    width=1100,
    font=dict(family='Arial, sans-serif')
)

# Add annotation with key stats
total_with_risk = len(rows)
high_risk = sum(1 for r in rows if (r['RISK_SCORE'] or 0) >= 30)
fig.add_annotation(
    text=f'<b>{total_with_risk:,}</b> US churches with FEMA risk scores<br>'
         f'<b>{high_risk:,}</b> in high-risk areas (score ≥ 30)<br>'
         f'18 hazard types: hurricane, flood, wildfire, earthquake, tornado & more',
    xref='paper', yref='paper',
    x=0.02, y=0.02,
    showarrow=False,
    bgcolor='rgba(255,255,255,0.9)',
    bordercolor='#ccc',
    borderwidth=1,
    font=dict(size=11)
)

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
map_path = OUT / "map_us_disaster_risk.png"
fig.write_image(str(map_path), scale=2)
print(f"Map saved: {map_path} ({map_path.stat().st_size/1024:.0f} KB)")

# Step 4: Also generate a state-level risk summary chart
state_df = pd.DataFrame([
    {'state': s, 'churches': d['count'], 'avg_risk': d['total_risk']/max(d['count'],1),
     'max_hurricane': d['max_hurricane'], 'max_flood': d['max_flood'], 'max_wildfire': d['max_wildfire']}
    for s, d in county_risk.items()
]).sort_values('avg_risk', ascending=False)

fig2 = px.bar(
    state_df.head(20),
    x='state', y='avg_risk',
    color='avg_risk',
    color_continuous_scale='RdYlGn_r',
    title='Top 20 States: Average FEMA Risk Score for Worship Sites',
    labels={'avg_risk': 'Avg FEMA Risk Score', 'state': 'State'}
)
fig2.update_layout(height=500, width=900)
bar_path = OUT / "map_us_disaster_risk_bars.png"
fig2.write_image(str(bar_path), scale=2)
print(f"Bar chart saved: {bar_path} ({bar_path.stat().st_size/1024:.0f} KB)")

db.close()
print("\n✅ Disaster risk map ready for outreach attachment")

# ── Print quick stats ──
print(f"\n=== HUMANITARIAN PITCH STATS ===")
print(f"US churches with FEMA scores: {total_with_risk:,}")
print(f"High-risk churches (≥30): {high_risk:,} ({high_risk/total_with_risk*100:.1f}%)")
print(f"States: {len(county_risk)}")
print(f"\nTop 10 high-risk states:")
for _, row in state_df.head(10).iterrows():
    print(f"  {row['state']:<4s} | {row['churches']:>5,} churches | avg risk {row['avg_risk']:.1f} | "
          f"hurricane {row['max_hurricane']:.0f} | flood {row['max_flood']:.0f} | wildfire {row['max_wildfire']:.0f}")

# Faith breakdown
faith_counts = Counter(r['faith'] for r in rows)
print(f"\nFaith breakdown (scored churches):")
for faith, count in faith_counts.most_common():
    print(f"  {faith}: {count:,}")

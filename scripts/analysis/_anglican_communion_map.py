"""Global Anglican Communion — interactive choropleth + scatter map."""
import sqlite3, json
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

DB = 'churches.db'
OUT = 'outputs/anglican_communion_map.html'

# Anglican traditions to include
ANGLICAN_TRADITIONS = [
    'Anglican', 'Episcopal', 'Episcopal and Anglican Churches',
    'Anglican/Episcopal', 'Anglican Church', 'Anglican Church of Canada',
    'Anglican Church in North America', 'Anglican Province of America',
    'Church of Uganda (Anglican)', 'Anglican (Church of South India)',
    'Protestant Episcopal', 'Reformed Episcopal Church',
    'Episcopal Church',
]

db = sqlite3.connect(DB)

# --- Query Anglican churches with GPS ---
placeholders = ','.join('?' * len(ANGLICAN_TRADITIONS))
df = pd.read_sql_query(f"""
    SELECT id, name, tradition, faith, latitude AS lat, longitude AS lon, country, city, state
    FROM churches
    WHERE tradition IN ({placeholders})
    AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND latitude != 0 AND longitude != 0
""", db, params=ANGLICAN_TRADITIONS)

# Normalize country codes: "United Kingdom" -> "GB"
COUNTRY_FIX = {'United Kingdom': 'GB', 'England': 'GB', 'Scotland': 'GB', 'Wales': 'GB',
               'Northern Ireland': 'GB', 'Great Britain': 'GB'}
df['country'] = df['country'].replace(COUNTRY_FIX)

print(f"Anglican churches with GPS: {len(df):,}")

# --- Country aggregation ---
country_counts = df.groupby('country').agg(
    churches=('id', 'count'),
    lat=('lat', 'median'),
    lon=('lon', 'median')
).reset_index()
country_counts = country_counts.sort_values('churches', ascending=False)
print(f"Countries: {len(country_counts)}")
print(country_counts.head(20).to_string(index=False))

# --- Build map ---
fig = go.Figure()

# Layer 1: Country choropleth
fig.add_trace(go.Choropleth(
    locations=country_counts['country'],
    locationmode='ISO-3',
    z=country_counts['churches'],
    colorscale='Blues',
    colorbar=dict(title='Anglican Churches', x=1.02),
    marker_line_color='white',
    marker_line_width=0.3,
    name='Country Total',
    hovertemplate='<b>%{location}</b><br>Anglican churches: %{z:,}<extra></extra>',
    zmin=1, zmax=country_counts['churches'].quantile(0.95),
))

# Layer 2: Scatter points for all countries (sample dense ones for perf)
for country in country_counts['country']:
    cdf = df[df['country'] == country]
    n = len(cdf)
    # Sample down dense countries to keep the map responsive
    if n > 3000:
        cdf = cdf.sample(min(n, 3000), random_state=42)
    
    fig.add_trace(go.Scattergeo(
        lon=cdf['lon'],
        lat=cdf['lat'],
        mode='markers',
        marker=dict(size=2.5 if n < 500 else 1.5, opacity=0.5, color='darkred'),
        name=f'{country} ({n:,})',
        text=cdf['name'],
        hovertemplate='<b>%{text}</b><br>%{lat:.3f}, %{lon:.3f}<extra></extra>',
    ))

# Layer 3: Country labels for top 8
top8 = country_counts.head(8)
fig.add_trace(go.Scattergeo(
    lon=top8['lon'],
    lat=top8['lat'],
    mode='text',
    text=[f"<b>{r['country']}</b><br>{r['churches']:,}" for _, r in top8.iterrows()],
    textfont=dict(size=10, color='#333'),
    name='Top Countries',
    hoverinfo='skip',
))

fig.update_layout(
    title=dict(
        text=f'<b>Global Anglican Communion</b><br><sub>{len(df):,} churches across {len(country_counts)} countries</sub>',
        x=0.5, xanchor='center',
        font=dict(size=20)
    ),
    geo=dict(
        projection_type='natural earth',
        showcoastlines=True, coastlinecolor='#444',
        showland=True, landcolor='#f5f5f0',
        showocean=True, oceancolor='#e8f4f8',
        showcountries=True, countrycolor='#ccc',
        showframe=False,
    ),
    margin=dict(l=10, r=10, t=80, b=10),
    width=1400, height=750,
)

fig.write_html(OUT)
print(f"\nSaved: {OUT}")

# --- Summary ---
print(f"\n{'='*60}")
print("Top 15 Anglican Countries")
print(f"{'='*60}")
for _, r in country_counts.head(15).iterrows():
    pct = r['churches'] / len(df) * 100
    print(f"  {r['country']:>4s}: {r['churches']:>8,} ({pct:5.1f}%)")

# Tradition breakdown
print(f"\n{'='*60}")
print("Tradition Breakdown")
print(f"{'='*60}")
for tradition, count in df['tradition'].value_counts().items():
    print(f"  {tradition}: {count:,}")

db.close()

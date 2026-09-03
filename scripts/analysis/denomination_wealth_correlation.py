"""
Denomination-Wealth Correlation Analysis
========================================
Analyzes which denominations are associated with wealthier vs. poorer areas.
Uses county-level census data joined to churches, computes relative wealth index,
and generates interactive visualizations.

Output:
  - outputs/denomination_wealth_ranking.csv
  - outputs/denomination_wealth.html (interactive Plotly chart)
  - outputs/denomination_wealth_scatter.html (income vs poverty scatter)
"""

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

print("Loading data...")
db = sqlite3.connect('E:/grid/churches.db')

# National county averages for normalization
nat_avg = db.execute("""
    SELECT 
        AVG(median_hh_income), AVG(poverty_rate), AVG(unemployment_rate),
        AVG(income_per_capita), AVG(bachelors_25_64), AVG(median_home_value),
        AVG(gini_index)
    FROM county_census_us 
    WHERE median_hh_income IS NOT NULL
""").fetchone()

NAT_INCOME = nat_avg[0]  # ~63,278
NAT_POVERTY = nat_avg[1]  # ~14.7
NAT_UNEMP = nat_avg[2]   # ~5.4
NAT_PCI = nat_avg[3]     # ~16,191
NAT_BACH = nat_avg[4] or 0
NAT_HOME = nat_avg[5] or 0
NAT_GINI = nat_avg[6] or 0

print(f"  National avg HH income: ${NAT_INCOME:,.0f}")
print(f"  National avg poverty: {NAT_POVERTY:.1f}%")
print(f"  National avg unemployment: {NAT_UNEMP:.1f}%")

# Main query: join churches with county census data, group by tradition
print("\nComputing denomination-level statistics...")
query = """
    SELECT 
        c.tradition,
        c.faith,
        c.taxonomy_id,
        COUNT(*) as church_count,
        ROUND(AVG(cc.median_hh_income), 0) as avg_hh_income,
        ROUND(AVG(cc.poverty_rate), 2) as avg_poverty,
        ROUND(AVG(cc.unemployment_rate), 2) as avg_unemployment,
        ROUND(AVG(cc.income_per_capita), 0) as avg_pci,
        ROUND(AVG(cc.bachelors_25_64), 2) as avg_bachelors,
        ROUND(AVG(cc.median_home_value), 0) as avg_home_value,
        ROUND(AVG(cc.gini_index), 4) as avg_gini,
        ROUND(AVG(cc.median_age), 1) as avg_age,
        ROUND(AVG(cc.white_pct), 2) as avg_white_pct,
        ROUND(AVG(cc.black_pct), 2) as avg_black_pct,
        ROUND(AVG(cc.hispanic_pct), 2) as avg_hispanic_pct,
        ROUND(AVG(cc.asian_pct), 2) as avg_asian_pct,
        -- Weighted by church count: what % of denomination churches are in high-poverty counties
        ROUND(SUM(CASE WHEN cc.poverty_rate > 20 THEN 1.0 ELSE 0 END) / COUNT(*), 4) as pct_high_poverty,
        ROUND(SUM(CASE WHEN cc.poverty_rate <= 10 THEN 1.0 ELSE 0 END) / COUNT(*), 4) as pct_low_poverty,
        ROUND(SUM(CASE WHEN cc.median_hh_income > 80000 THEN 1.0 ELSE 0 END) / COUNT(*), 4) as pct_high_income,
        ROUND(SUM(CASE WHEN cc.median_hh_income < 45000 THEN 1.0 ELSE 0 END) / COUNT(*), 4) as pct_low_income
    FROM churches c
    JOIN county_census_us cc ON c.county_fips_5 = cc.county_fips
    WHERE c.country='US' AND cc.median_hh_income IS NOT NULL
    GROUP BY c.tradition, c.faith, c.taxonomy_id
    HAVING church_count >= 100
    ORDER BY avg_hh_income DESC
"""

df = pd.read_sql_query(query, db)
db.close()

# Compute relative indices
df['income_index'] = df['avg_hh_income'] / NAT_INCOME  # >1 = wealthier than avg
df['poverty_index'] = df['avg_poverty'] / NAT_POVERTY   # <1 = less poverty than avg
df['wealth_score'] = (df['income_index'] - df['poverty_index']) * 100  # composite

print(f"\n  {len(df)} denominations with 100+ churches analyzed")
print(f"  Income range: ${df['avg_hh_income'].min():,.0f} - ${df['avg_hh_income'].max():,.0f}")

# ---- RANKING TABLES ----

print("\n" + "="*90)
print("TOP 15: WEALTH-LINKED DENOMINATIONS (highest avg county income)")
print("="*90)
top = df.nlargest(15, 'avg_hh_income')
for _, r in top.iterrows():
    print(f"  {r['tradition']:35s} | ${r['avg_hh_income']:>8,.0f} | {r['avg_poverty']:>5.1f}% pov | "
          f"${r['avg_pci']:>7,.0f} PCI | {r['church_count']:>5,} ch | idx={r['income_index']:.2f}")

print("\n" + "="*90)
print("BOTTOM 15: POVERTY-LINKED DENOMINATIONS (lowest avg county income)")
print("="*90)
bottom = df.nsmallest(15, 'avg_hh_income')
for _, r in bottom.iterrows():
    print(f"  {r['tradition']:35s} | ${r['avg_hh_income']:>8,.0f} | {r['avg_poverty']:>5.1f}% pov | "
          f"${r['avg_pci']:>7,.0f} PCI | {r['church_count']:>5,} ch | idx={r['income_index']:.2f}")

# ---- COMPOSITE WEALTH SCORE ----
print("\n" + "="*90)
print("TOP 15 BY COMPOSITE WEALTH SCORE (income↑ + poverty↓)")
print("="*90)
for _, r in df.nlargest(15, 'wealth_score').iterrows():
    print(f"  {r['tradition']:35s} | score={r['wealth_score']:>6.1f} | ${r['avg_hh_income']:>8,.0f} | "
          f"{r['avg_poverty']:>5.1f}% pov | {r['church_count']:>5,} ch")

print("\n" + "="*90)
print("BOTTOM 15 BY COMPOSITE WEALTH SCORE (income↓ + poverty↑)")
print("="*90)
for _, r in df.nsmallest(15, 'wealth_score').iterrows():
    print(f"  {r['tradition']:35s} | score={r['wealth_score']:>6.1f} | ${r['avg_hh_income']:>8,.0f} | "
          f"{r['avg_poverty']:>5.1f}% pov | {r['church_count']:>5,} ch")

# Save CSV
csv_path = OUTPUT_DIR / 'denomination_wealth_ranking.csv'
df.to_csv(csv_path, index=False)
print(f"\n✅ Saved CSV: {csv_path}")

# ---- VISUALIZATION 1: Income ranking bar chart ----
print("\nGenerating visualizations...")

# Filter for denominations with 200+ churches for cleaner viz
df_viz = df[df['church_count'] >= 200].copy()

fig1 = go.Figure()

# Top 25 by income
fig1.add_trace(go.Bar(
    y=[f"{r['tradition']} ({r['faith'][:3]})" for _, r in df_viz.nlargest(25, 'avg_hh_income').iterrows()],
    x=df_viz.nlargest(25, 'avg_hh_income')['avg_hh_income'],
    orientation='h',
    name='Highest Income',
    marker_color='#1a5276',
    hovertemplate='%{y}: $%{x:,.0f}<extra></extra>'
))

fig1.add_vline(x=NAT_INCOME, line_dash="dash", line_color="gray", 
               annotation_text=f"US Avg ${NAT_INCOME:,.0f}")

fig1.update_layout(
    title="<b>Denominations in Wealthiest Counties</b><br><sub>Average median household income of counties where churches are located</sub>",
    xaxis_title="Average County Median Household Income ($)",
    yaxis_title="",
    height=700,
    template='plotly_white',
    showlegend=False,
    margin=dict(l=20, r=20, t=80, b=20)
)

fig1.write_html(OUTPUT_DIR / 'denomination_wealth.html')
print(f"  ✅ {OUTPUT_DIR / 'denomination_wealth.html'}")

# ---- VISUALIZATION 2: Poverty ranking ----
fig2 = go.Figure()

fig2.add_trace(go.Bar(
    y=[f"{r['tradition']} ({r['faith'][:3]})" for _, r in df_viz.nlargest(25, 'avg_poverty').iterrows()],
    x=df_viz.nlargest(25, 'avg_poverty')['avg_poverty'],
    orientation='h',
    name='Highest Poverty',
    marker_color='#c0392b',
    hovertemplate='%{y}: %{x:.1f}% poverty<extra></extra>'
))

fig2.add_vline(x=NAT_POVERTY, line_dash="dash", line_color="gray",
               annotation_text=f"US Avg {NAT_POVERTY:.1f}%")

fig2.update_layout(
    title="<b>Denominations in Highest-Poverty Counties</b><br><sub>Average poverty rate of counties where churches are located</sub>",
    xaxis_title="Average County Poverty Rate (%)",
    yaxis_title="",
    height=700,
    template='plotly_white',
    showlegend=False,
    margin=dict(l=20, r=20, t=80, b=20)
)

fig2.write_html(OUTPUT_DIR / 'denomination_poverty.html')
print(f"  ✅ {OUTPUT_DIR / 'denomination_poverty.html'}")

# ---- VISUALIZATION 3: Income vs Poverty scatter (bubble chart) ----
fig3 = go.Figure()

# Color by faith
faith_colors = {
    'Christian': '#1f77b4', 'Islam': '#2ca02c', 'Judaism': '#9467bd',
    'Buddhist': '#ff7f0e', 'Hindu': '#d62728', 'Other': '#8c564b',
    'Shinto': '#e377c2', 'Sikh': '#bcbd22', 'Taoist': '#17becf',
    'Jain': '#7f7f7f', 'Baháʼí': '#dbdb8d', 'Confucian': '#9edae5'
}

fig3.add_trace(go.Scatter(
    x=df_viz['avg_hh_income'],
    y=df_viz['avg_poverty'],
    mode='markers+text',
    text=[r['tradition'] if r['church_count'] >= 2000 or r['avg_hh_income'] > 85000 
          or r['avg_poverty'] > 20 else '' for _, r in df_viz.iterrows()],
    textposition='top center',
    textfont=dict(size=9),
    marker=dict(
        size=df_viz['church_count'].clip(50, 5000) / 5000 * 50 + 5,
        color=[faith_colors.get(str(f), '#999') for f in df_viz['faith']],
        opacity=0.7,
        line=dict(width=0.5, color='white')
    ),
    hovertemplate=(
        '<b>%{text}</b><br>'
        'Faith: ' + df_viz['faith'].astype(str) + '<br>'
        'Income: $%{x:,.0f}<br>'
        'Poverty: %{y:.1f}%<br>'
        'Churches: ' + df_viz['church_count'].astype(str) + '<br>'
        '<extra></extra>'
    )
))

fig3.add_hline(y=NAT_POVERTY, line_dash="dash", line_color="gray", 
               annotation_text=f"US Avg Poverty {NAT_POVERTY:.1f}%")
fig3.add_vline(x=NAT_INCOME, line_dash="dash", line_color="gray",
               annotation_text=f"US Avg Income ${NAT_INCOME:,.0f}")

fig3.update_layout(
    title="<b>Denomination Wealth-Poverty Landscape</b><br><sub>Bubble size = number of churches. Labeled: large denominations + outliers.</sub>",
    xaxis_title="Average County Median Household Income ($)",
    yaxis_title="Average County Poverty Rate (%)",
    height=800,
    template='plotly_white',
    showlegend=False,
    margin=dict(l=20, r=20, t=80, b=20)
)

fig3.write_html(OUTPUT_DIR / 'denomination_wealth_scatter.html')
print(f"  ✅ {OUTPUT_DIR / 'denomination_wealth_scatter.html'}")

# ---- VISUALIZATION 4: Composite Wealth Score Heatmap ----
fig4 = go.Figure()

df_score = df_viz.nlargest(30, 'wealth_score').copy()
df_score['label'] = df_score['tradition'] + ' (' + df_score['faith'].str[:3] + ')'

fig4.add_trace(go.Bar(
    y=df_score['label'],
    x=df_score['wealth_score'],
    orientation='h',
    marker=dict(
        color=df_score['wealth_score'],
        colorscale='RdYlGn',
        showscale=True,
        colorbar=dict(title='Wealth Score')
    ),
    hovertemplate='%{y}: Score=%{x:.1f}<extra></extra>'
))

fig4.update_layout(
    title="<b>Composite Wealth Score by Denomination</b><br><sub>Higher = wealthier counties + lower poverty. (Income index - Poverty index) × 100</sub>",
    xaxis_title="Wealth Score (higher = wealthier surroundings)",
    yaxis_title="",
    height=750,
    template='plotly_white',
    showlegend=False,
    margin=dict(l=20, r=20, t=80, b=20)
)

fig4.write_html(OUTPUT_DIR / 'denomination_wealth_score.html')
print(f"  ✅ {OUTPUT_DIR / 'denomination_wealth_score.html'}")

# ---- SUMMARY STATS BY FAITH ----
print("\n" + "="*90)
print("WEALTH SUMMARY BY FAITH CATEGORY")
print("="*90)
faith_stats = df.groupby('faith').agg(
    churches=('church_count', 'sum'),
    avg_income=('avg_hh_income', lambda x: (x * df.loc[x.index, 'church_count']).sum() / df.loc[x.index, 'church_count'].sum()),
    avg_poverty=('avg_poverty', lambda x: (x * df.loc[x.index, 'church_count']).sum() / df.loc[x.index, 'church_count'].sum()),
).sort_values('avg_income', ascending=False)

for faith, r in faith_stats.iterrows():
    idx = r['avg_income'] / NAT_INCOME
    print(f"  {faith:15s} | {r['churches']:>8,.0f} ch | ${r['avg_income']:>8,.0f} income ({idx:.2f}x natl) | "
          f"{r['avg_poverty']:.1f}% poverty")

print(f"\n  {'US NATIONAL AVG':15s} | {'':>8s} | ${NAT_INCOME:>8,.0f} income (1.00x) | {NAT_POVERTY:.1f}% poverty")

print("\n" + "="*90)
print("ALL OUTPUTS:")
print(f"  {csv_path}")
print(f"  {OUTPUT_DIR / 'denomination_wealth.html'}")
print(f"  {OUTPUT_DIR / 'denomination_poverty.html'}")
print(f"  {OUTPUT_DIR / 'denomination_wealth_scatter.html'}")
print(f"  {OUTPUT_DIR / 'denomination_wealth_score.html'}")
print("\nDone!")

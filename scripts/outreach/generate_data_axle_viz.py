"""
Generate visualizations for Data Axle pitch:
1. US churches by county median income heatmap
2. Global faith distribution map
3. US denominational density
"""
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
from pathlib import Path

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)

db = sqlite3.connect("E:/grid/churches.db")

# ============================================================
# 1. US CHURCHES BY COUNTY MEDIAN INCOME
# ============================================================
print("Generating income heatmap...")

df_income = pd.read_sql("""
    SELECT 
        ce.county_fips_5 as fips,
        ce.county_name,
        ce.county_median_hh_income as median_income,
        ce.county_total_pop as population,
        COUNT(c.id) as church_count
    FROM churches c
    JOIN church_enrichment ce ON ce.church_id = c.id
    WHERE c.country = 'US'
      AND ce.county_median_hh_income IS NOT NULL
      AND ce.county_fips_5 IS NOT NULL
    GROUP BY ce.county_fips_5
    HAVING church_count >= 5
""", db)

df_income["income_bracket"] = pd.cut(
    df_income["median_income"],
    bins=[0, 40000, 55000, 70000, 85000, 100000, 120000, 250000],
    labels=["<$40K", "$40-55K", "$55-70K", "$70-85K", "$85-100K", "$100-120K", "$120K+"]
)

fig_income = px.choropleth(
    df_income,
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations="fips",
    color="median_income",
    color_continuous_scale="Viridis",
    scope="usa",
    labels={"median_income": "Median Household Income", "church_count": "Churches"},
    hover_data={"county_name": True, "median_income": ":$," , "church_count": True, "population": ":,"},
    title="US Churches by County Median Household Income<br><sup>GRID — Global Religious Infrastructure Database</sup>"
)
fig_income.update_layout(height=600, margin={"r":0,"t":50,"l":0,"b":0})
fig_income.write_html(OUT / "map_income_churches.html")
print(f"  -> {OUT / 'map_income_churches.html'} ({len(df_income):,} counties)")

# ============================================================
# 2. GLOBAL FAITH DISTRIBUTION
# ============================================================
print("Generating global faith map...")

df_global = pd.read_sql("""
    SELECT country, faith, COUNT(*) as cnt
    FROM churches
    WHERE latitude IS NOT NULL
    GROUP BY country, faith
""", db)

# Get dominant faith per country
df_dominant = pd.read_sql("""
    SELECT country, faith, cnt FROM (
        SELECT country, faith, COUNT(*) as cnt,
               ROW_NUMBER() OVER (PARTITION BY country ORDER BY COUNT(*) DESC) as rn
        FROM churches WHERE latitude IS NOT NULL
        GROUP BY country, faith
    ) WHERE rn = 1
""", db)

# Total per country
df_total = pd.read_sql("""
    SELECT country, COUNT(*) as total FROM churches WHERE latitude IS NOT NULL GROUP BY country
""", db)

# Color map
faith_colors = {
    "Christian": "#6BAED6",
    "Islam": "#2CA02C",
    "Hindu": "#FF7F0E",
    "Buddhist": "#D62728",
    "Shinto": "#9467BD",
    "Judaism": "#8C564B",
    "Sikh": "#E377C2",
    "Taoist": "#7F7F7F",
    "Other": "#BCBD22",
}

df_dominant["color"] = df_dominant["faith"].map(faith_colors).fillna("#BCBD22")

fig_global = px.scatter_geo(
    df_dominant.merge(df_total, on="country"),
    locations="country",
    locationmode="country names",
    color="faith",
    size="total",
    size_max=40,
    color_discrete_map=faith_colors,
    hover_name="country",
    hover_data={"total": ":,", "faith": True},
    title="Global Religious Infrastructure — Dominant Faith by Country<br><sup>GRID — 3.4M worship sites across 291 countries</sup>",
    projection="natural earth"
)
fig_global.update_layout(height=600, margin={"r":0,"t":50,"l":0,"b":0})
fig_global.write_html(OUT / "map_global_dominant.html")
print(f"  -> {OUT / 'map_global_dominant.html'} ({len(df_dominant)} countries)")

# ============================================================
# 3. US DENOMINATIONAL DENSITY — TOP 5 CHRISTIAN TRADITIONS
# ============================================================
print("Generating denominational density...")

traditions = ["Baptist", "Catholic", "Methodist", "Lutheran", "Pentecostal"]
df_denom = pd.read_sql("""
    SELECT 
        ce.county_fips_5 as fips,
        ce.county_name,
        c.tradition,
        COUNT(*) as cnt
    FROM churches c
    JOIN church_enrichment ce ON ce.church_id = c.id
    WHERE c.country = 'US'
      AND c.tradition IN ('Baptist','Catholic','Methodist','Lutheran','Pentecostal')
      AND ce.county_fips_5 IS NOT NULL
    GROUP BY ce.county_fips_5, c.tradition
""", db)

# Pivot: one column per tradition
df_pivot = df_denom.pivot(index="fips", columns="tradition", values="cnt").fillna(0).reset_index()

# Add the dominant tradition
df_pivot["dominant"] = df_pivot[traditions].idxmax(axis=1)
df_pivot["max_count"] = df_pivot[traditions].max(axis=1)

fig_denom = px.choropleth(
    df_pivot,
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations="fips",
    color="dominant",
    color_discrete_map={
        "Baptist": "#1f77b4",
        "Catholic": "#d62728",
        "Methodist": "#2ca02c",
        "Lutheran": "#9467bd",
        "Pentecostal": "#ff7f0e",
    },
    scope="usa",
    hover_data={**{t: True for t in traditions}, "dominant": False},
    title="Dominant Christian Tradition by US County<br><sup>GRID — Which denomination dominates each county?</sup>",
    category_orders={"dominant": traditions}
)
fig_denom.update_layout(height=600, margin={"r":0,"t":50,"l":0,"b":0})
fig_denom.write_html(OUT / "map_denom_dominance.html")
print(f"  -> {OUT / 'map_denom_dominance.html'} ({len(df_pivot):,} counties)")

# ============================================================
# 4. CHURCHES PER CAPITA (market density for Data Axle)
# ============================================================
print("Generating churches per capita...")

df_density = pd.read_sql("""
    SELECT 
        ce.county_fips_5 as fips,
        ce.county_name,
        ce.county_total_pop as population,
        COUNT(c.id) as churches,
        CAST(COUNT(c.id) AS REAL) / NULLIF(ce.county_total_pop, 0) * 10000 as churches_per_10k
    FROM churches c
    JOIN church_enrichment ce ON ce.church_id = c.id
    WHERE c.country = 'US'
      AND ce.county_total_pop > 1000
      AND ce.county_fips_5 IS NOT NULL
    GROUP BY ce.county_fips_5
""", db)

fig_density = px.choropleth(
    df_density,
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations="fips",
    color="churches_per_10k",
    color_continuous_scale="YlOrRd",
    scope="usa",
    range_color=(0, 30),
    labels={"churches_per_10k": "Churches per 10K people", "churches": "Total Churches"},
    hover_data={"county_name": True, "churches": True, "population": ":,", "churches_per_10k": ":.1f"},
    title="Church Density: Worship Sites per 10,000 People<br><sup>GRID — Identify over-served and under-served markets</sup>",
)
fig_density.update_layout(height=600, margin={"r":0,"t":50,"l":0,"b":0})
fig_density.write_html(OUT / "map_church_density.html")
print(f"  -> {OUT / 'map_church_density.html'} ({len(df_density):,} counties)")

db.close()
print("\n✅ All 4 visualizations generated!")

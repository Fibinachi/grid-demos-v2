"""
Generate visualizations for Data Axle pitch — using correct tables.
"""
import sqlite3
import plotly.express as px
import pandas as pd
from pathlib import Path

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect("E:/grid/churches.db")

# 1. US CHURCHES BY CENSUS TRACT MEDIAN INCOME
print("1/4 Income heatmap...")
df_income = pd.read_sql("""
    SELECT c.id, c.name, c.city, c.state, c.latitude, c.longitude,
           ca.acs_median_income as median_income, ca.acs_total_pop,
           ca.acs_poverty_rate, ca.acs_median_home_value
    FROM churches c
    JOIN church_census_us ca ON ca.church_id = c.id
    WHERE c.country='US' AND c.latitude IS NOT NULL AND ca.acs_median_income IS NOT NULL
""", db)
print(f"   {len(df_income):,} churches with income data")

sample = df_income.sample(n=min(80000, len(df_income)), random_state=42)
fig = px.scatter_mapbox(
    sample, lat="latitude", lon="longitude", color="median_income",
    color_continuous_scale="Viridis", size_max=6, zoom=3, height=650, opacity=0.5,
    labels={"median_income": "Median Household Income ($)"},
    hover_data={"name": True, "city": True, "state": True, "median_income": ":$,"},
    title="<b>Every Dot is a Church — Colored by Neighborhood Income</b><br><sup>GRID: 233K churches with Census tract income. Green=affluent. Purple=low-income.</sup>",
    mapbox_style="carto-darkmatter",
)
fig.update_layout(margin={"r":0,"t":60,"l":0,"b":0})
fig.write_html(OUT / "map_income_churches.html")
print("   -> map_income_churches.html")

# 2. GLOBAL FAITH
print("2/4 Global faith map...")
df_dom = pd.read_sql("""
    SELECT country, faith, cnt FROM (
        SELECT country, faith, COUNT(*) as cnt,
               ROW_NUMBER() OVER (PARTITION BY country ORDER BY COUNT(*) DESC) as rn
        FROM churches WHERE latitude IS NOT NULL GROUP BY country, faith
    ) WHERE rn=1
""", db)
faith_colors = {"Christian":"#6BAED6","Islam":"#2CA02C","Hindu":"#FF7F0E","Buddhist":"#D62728","Shinto":"#9467BD","Judaism":"#8C564B","Sikh":"#E377C2","Taoist":"#7F7F7F","Other":"#BCBD22"}
fig = px.choropleth(df_dom, locations="country", locationmode="country names", color="faith",
    color_discrete_map=faith_colors, hover_name="country", hover_data={"cnt": ":,"},
    title="<b>Dominant Religion by Country</b><br><sup>GRID — 3.4M worship sites across 291 countries</sup>")
fig.update_layout(height=550, margin={"r":0,"t":60,"l":0,"b":0})
fig.write_html(OUT / "map_global_dominant.html")
print(f"   -> map_global_dominant.html ({len(df_dom)} countries)")

# 3. DENOMINATIONAL DOMINANCE
print("3/4 Denominational dominance...")
df_den = pd.read_sql("""
    SELECT c.county_fips_5 as fips, c.tradition, COUNT(*) as cnt
    FROM churches c WHERE c.country='US' AND c.county_fips_5 IS NOT NULL
      AND c.tradition IN ('Baptist','Catholic','Methodist','Lutheran','Pentecostal','Non-denominational','Presbyterian','Episcopal')
    GROUP BY c.county_fips_5, c.tradition
""", db)
df_piv = df_den.pivot(index="fips", columns="tradition", values="cnt").fillna(0).reset_index()
trads = [t for t in ['Baptist','Catholic','Methodist','Lutheran','Pentecostal','Non-denominational','Presbyterian','Episcopal'] if t in df_piv.columns]
df_piv["dominant"] = df_piv[trads].idxmax(axis=1)
fig = px.choropleth(df_piv, geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations="fips", color="dominant", scope="usa",
    color_discrete_map={"Baptist":"#1f77b4","Catholic":"#d62728","Methodist":"#2ca02c","Lutheran":"#9467bd","Pentecostal":"#ff7f0e","Non-denominational":"#8c564b","Presbyterian":"#e377c2","Episcopal":"#17becf"},
    hover_data={**{t:True for t in trads}, "dominant": False},
    title="<b>Dominant Christian Tradition by US County</b><br><sup>1M+ churches classified by denomination</sup>")
fig.update_layout(height=600, margin={"r":0,"t":60,"l":0,"b":0})
fig.write_html(OUT / "map_denom_dominance.html")
print(f"   -> map_denom_dominance.html ({len(df_piv):,} counties)")

# 4. CHURCHES PER CAPITA
print("4/4 Church density...")
df_dens = pd.read_sql("""
    SELECT c.county_fips_5 as fips, MAX(ca.acs_total_pop) as pop, COUNT(*) as churches,
           CAST(COUNT(*) AS REAL)/NULLIF(MAX(ca.acs_total_pop),0)*10000 as per_10k
    FROM churches c JOIN church_census_us ca ON ca.church_id=c.id
    WHERE c.country='US' AND c.county_fips_5 IS NOT NULL AND ca.acs_total_pop>1000
    GROUP BY c.county_fips_5
""", db)
fig = px.choropleth(df_dens, geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    locations="fips", color="per_10k", color_continuous_scale="YlOrRd", scope="usa", range_color=(0,25),
    labels={"per_10k":"Churches per 10K people"},
    hover_data={"churches":True,"pop":":,","per_10k":":.1f"},
    title="<b>Church Density: Worship Sites per 10,000 People</b><br><sup>Find over-served & under-served markets</sup>")
fig.update_layout(height=600, margin={"r":0,"t":60,"l":0,"b":0})
fig.write_html(OUT / "map_church_density.html")
print(f"   -> map_church_density.html ({len(df_dens):,} counties)")

db.close()
print("\nDone!")

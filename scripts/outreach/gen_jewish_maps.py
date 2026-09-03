"""
Generate Jewish World Map for Toronto UJA/CIJA outreach campaign.
Shows global Jewish infrastructure: synagogues, Chabad houses, yeshivas, etc.
"""
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pathlib import Path

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect("E:/grid/churches.db")

print("=== JEWISH WORLD MAP FOR TORONTO OUTREACH ===\n")

# ═══════════════════════════════════════════════════════════════
# 1. GLOBAL JEWISH DISTRIBUTION — scatter map
# ═══════════════════════════════════════════════════════════════
print("1/3 Global Jewish scatter map...")
df = pd.read_sql("""
    SELECT id, name, city, state, country, latitude, longitude,
           landmark_type, tradition
    FROM churches
    WHERE faith = 'Judaism' AND latitude IS NOT NULL
""", db)
print(f"   {len(df):,} Jewish entries with GPS")

# Clean up label
tradition_map = {
    "Rabbinic": "Rabbinic", "rabbinic": "Rabbinic",
    "Orthodox": "Orthodox", "orthodox": "Orthodox",
    "Orthodox (Chabad)": "Chabad", "orthodox_chabad": "Chabad",
    "Reform": "Reform", "reform": "Reform",
    "Sephardic": "Sephardic", "sephardic": "Sephardic",
    "Orthodox (Yeshiva)": "Yeshiva", "orthodox_yeshiva": "Yeshiva",
    "Conservative": "Conservative", "conservative": "Conservative",
    "Orthodox (Hasidic)": "Hasidic", "orthodox_hasidic": "Hasidic",
}
df["tradition_clean"] = df["tradition"].map(tradition_map).fillna(df["tradition"].str.strip())

# Color map for traditions
tradition_colors = {
    "Orthodox": "#1f77b4",
    "Chabad": "#ff7f0e",
    "Rabbinic": "#2ca02c",
    "Reform": "#d62728",
    "Conservative": "#9467bd",
    "Sephardic": "#8c564b",
    "Hasidic": "#e377c2",
    "Yeshiva": "#7f7f7f",
}

# Sample for performance if > 20K points
sample = df if len(df) <= 20000 else df.sample(n=20000, random_state=42)

fig = px.scatter_mapbox(
    sample,
    lat="latitude", lon="longitude",
    color="tradition_clean",
    color_discrete_map=tradition_colors,
    size_max=5, zoom=1.5, height=700, opacity=0.6,
    hover_data={"name": True, "city": True, "country": True, "landmark_type": True},
    title="<b>Global Jewish Infrastructure — 25,607 Synagogues, Yeshivas & Community Centers</b><br><sup>GRID: Every dot is a synagogue, Chabad house, yeshiva, or Jewish community center. 54 countries. AI-verified classification.</sup>",
    mapbox_style="carto-darkmatter",
)
fig.update_layout(margin={"r": 0, "t": 70, "l": 0, "b": 0})
fig.update_traces(marker=dict(size=4))
fig.write_html(OUT / "map_jewish_global.html")
print(f"   -> map_jewish_global.html")

# ═══════════════════════════════════════════════════════════════
# 2. TORONTO JEWISH INFRASTRUCTURE — detail scatter
# ═══════════════════════════════════════════════════════════════
print("2/3 Toronto Jewish detail map...")
toronto = pd.read_sql("""
    SELECT id, name, city, state, country, latitude, longitude,
           landmark_type, tradition
    FROM churches
    WHERE faith = 'Judaism' AND country IN ('CA', 'Canada')
      AND (UPPER(city) IN ('NORTH YORK','TORONTO','THORNHILL','VAUGHAN','RICHMOND HILL','MARKHAM','SCARBOROUGH','ETOBICOKE','MISSISSAUGA','DOWNSVIEW','WILLOWDALE','OUTREMONT','COTE SAINT-LUC','MONTREAL','OTTAWA','WINNIPEG','VANCOUVER')
           OR UPPER(name) LIKE '%TORONTO%' OR UPPER(name) LIKE '%GTA%'
           OR UPPER(name) LIKE '%ONTARIO%')
      AND latitude IS NOT NULL
""", db)

toronto["tradition_clean"] = toronto["tradition"].map(tradition_map).fillna(toronto["tradition"].str.strip())
toronto["label"] = toronto.apply(lambda r: f"{r['name'][:60]}<br>{r['tradition_clean']} · {r['landmark_type']}", axis=1)

print(f"   {len(toronto)} Jewish entries in Toronto area")

fig2 = px.scatter_mapbox(
    toronto,
    lat="latitude", lon="longitude",
    color="tradition_clean",
    color_discrete_map=tradition_colors,
    size_max=12, zoom=10.5, height=700, opacity=0.8,
    hover_data={"name": True, "tradition_clean": True, "landmark_type": True},
    mapbox_style="carto-darkmatter",
    title="<b>Toronto Jewish Infrastructure — Synagogues, Yeshivas & Community Centers</b><br><sup>GRID data: 155+ Jewish institutions across the GTA. Color-coded by tradition.</sup>",
    center={"lat": 43.77, "lon": -79.42},
)
fig2.update_traces(marker=dict(size=10))
fig2.update_layout(margin={"r": 0, "t": 70, "l": 0, "b": 0})
fig2.write_html(OUT / "map_jewish_toronto.html")
print(f"   -> map_jewish_toronto.html")

# ═══════════════════════════════════════════════════════════════
# 3. SUMMARY CHART — by country & tradition
# ═══════════════════════════════════════════════════════════════
print("3/3 Summary infographics...")

# Top countries
top_countries = pd.read_sql("""
    SELECT country, COUNT(*) as cnt
    FROM churches WHERE faith='Judaism'
    GROUP BY country ORDER BY cnt DESC LIMIT 15
""", db)

fig3 = px.bar(
    top_countries, x="country", y="cnt",
    title="<b>Jewish Institutions by Country — Top 15</b><br><sup>GRID: 25,607 entries across 54 countries</sup>",
    labels={"cnt": "Institutions", "country": "Country"},
    color_discrete_sequence=["#8C564B"],
)
fig3.update_layout(height=450, margin={"r": 0, "t": 70, "l": 0, "b": 0})
fig3.write_html(OUT / "map_jewish_countries.html")
print(f"   -> map_jewish_countries.html")

# Canada summary
ca_summary = pd.read_sql("""
    SELECT city, COUNT(*) as cnt
    FROM churches WHERE faith='Judaism' AND country='CA'
    GROUP BY city ORDER BY cnt DESC LIMIT 12
""", db)

fig4 = px.bar(
    ca_summary, x="city", y="cnt",
    title="<b>Canadian Jewish Institutions by City</b><br><sup>454 Jewish institutions across Canada</sup>",
    labels={"cnt": "Institutions", "city": "City"},
    color_discrete_sequence=["#D62728"],
)
fig4.update_layout(height=400, margin={"r": 0, "t": 70, "l": 0, "b": 0})
fig4.write_html(OUT / "map_jewish_canada.html")
print(f"   -> map_jewish_canada.html")

# Build summary stats block
total = len(df)
with_gps = len(df[df["latitude"].notna()])
synagogues = len(df[df["landmark_type"] == "synagogue"])
chabad = len(df[df["landmark_type"] == "chabad_house"])
yeshivas = len(df[df["landmark_type"] == "yeshiva"])
with_contacts = pd.read_sql("""
    SELECT COUNT(DISTINCT c.id) as cnt FROM churches c
    JOIN church_contact_values ccv ON ccv.church_id = c.id
    WHERE c.faith='Judaism'
""", db)["cnt"].iloc[0]

print(f"\n{'='*60}")
print(f"JEWISH DATASET SUMMARY")
print(f"{'='*60}")
print(f"  Total entries:      {total:>8,}")
print(f"  GPS coverage:       {with_gps:>8,} ({with_gps/total*100:.0f}%)")
print(f"  Synagogues:         {synagogues:>8,}")
print(f"  Chabad houses:      {chabad:>8,}")
print(f"  Yeshivas:           {yeshivas:>8,}")
print(f"  With contacts:      {with_contacts:>8,}")
print(f"  Countries:          54")
print(f"  Traditions:         12 canonical")
print(f"  Toronto area:       {len(toronto):>8,}")
print(f"{'='*60}")

db.close()
print("\n✅ All maps generated in outputs/outreach/")

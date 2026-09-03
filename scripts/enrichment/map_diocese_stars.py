"""
Diocese Star Map v2 — Colored diocese boundaries + star lines + red archdiocese/province borders.
"""
import sqlite3, csv, json, os
import folium
from scripts.visualization.map_utils import folium_default_layers
import geopandas as gpd

DB = 'churches.db'
CATHEDRAL_CSV = 'data/diocese_mapper/cathedral_list.csv'
BOUNDARIES_GEOJSON = 'data/diocese_mapper/diocese_boundaries_revised.geojson'
PROVINCE_GEOJSON = 'data/diocese_mapper/province_boundaries_revised.geojson'

# ── Colors ──
colors = [
    '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990', '#dcbeff',
    '#9a6324', '#fffac8', '#800000', '#aaffc3', '#808000', '#ffd8b1',
    '#000075', '#a9a9a9', '#e6beff', '#008080', '#ff4500', '#00ced1'
]
RED = '#e6194b'

# ── Load cathedral coordinates & identify archdioceses ──
print("Loading cathedrals...")
cathedrals = {}
archdioceses = set()
with open(CATHEDRAL_CSV, 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        diocese = row['Diocese'].strip()
        province = row.get('Province', '').strip()
        if diocese == province:
            archdioceses.add(diocese)
        try:
            coords = json.loads(row['Cathedral_coord_list'])
            names = json.loads(row['Cathedral_List'])
        except:
            continue
        cathedrals[diocese] = [(c[0], c[1], n) for c, n in zip(coords, names)]
print(f"  {len(cathedrals)} dioceses, {len(archdioceses)} archdioceses")

# ── Load parishes ──
print("Loading parishes...")
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""
    SELECT ch.latitude, ch.longitude, ce.diocese
    FROM churches ch
    JOIN church_enrichment ce ON ce.church_id = ch.id
    WHERE ch.country='US'
      AND ch.latitude IS NOT NULL AND ch.longitude IS NOT NULL
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese IS NOT NULL AND ce.diocese != ''
""")
parishes = {}
for lat, lon, diocese in c.fetchall():
    parishes.setdefault(diocese, []).append((lat, lon))
conn.close()
print(f"  {sum(len(v) for v in parishes.values()):,} parishes in {len(parishes)} dioceses")

# ── Color mapping ──
all_names = sorted(set(list(parishes.keys()) + list(cathedrals.keys())))
color_map = {d: colors[i % len(colors)] for i, d in enumerate(all_names)}

# ── Build map ──
print("Building map...")
m = folium.Map(location=[39.8, -98.5], zoom_start=5, tiles=None, control_scale=True)
folium_default_layers(m)

# ── 1. Province boundaries (red, thick) ──
print("  Adding province borders (red)...")
provinces = gpd.read_file(PROVINCE_GEOJSON)
folium.GeoJson(
    provinces, name='Provinces (Red)',
    style_function=lambda x: {'color': RED, 'weight': 2.5, 'fillOpacity': 0},
    tooltip=folium.GeoJsonTooltip(fields=['Province'], aliases=['Province:'])
).add_to(m)

# ── 2. Diocese boundaries colored to match stars ──
print("  Adding diocese boundaries...")
diocese_gdf = gpd.read_file(BOUNDARIES_GEOJSON)

def diocese_style(feature):
    name = feature['properties'].get('Diocese', '')
    c = color_map.get(name, '#888888')
    is_arch = name in archdioceses
    return {
        'fillColor': c,
        'fillOpacity': 0.12,
        'color': RED if is_arch else c,
        'weight': 2.5 if is_arch else 1,
        'dashArray': None if is_arch else '3 6'
    }

folium.GeoJson(
    diocese_gdf, name='Dioceses',
    style_function=diocese_style,
    tooltip=folium.GeoJsonTooltip(fields=['Diocese'], aliases=['Diocese:'])
).add_to(m)

# ── 3. Star lines (parish → cathedral) ──
print("  Drawing star lines...")
lines_drawn = 0
star_fg = folium.FeatureGroup(name='Parish→Cathedral Lines')
for diocese, parish_list in parishes.items():
    if diocese not in cathedrals:
        continue
    color = color_map.get(diocese, '#ffffff')
    cath_lat, cath_lon, cath_name = cathedrals[diocese][0]
    for lat, lon in parish_list:
        if lat and lon:
            folium.PolyLine(
                [(lat, lon), (cath_lat, cath_lon)],
                color=color, weight=1, opacity=0.35
            ).add_to(star_fg)
            lines_drawn += 1
star_fg.add_to(m)
print(f"    {lines_drawn:,} lines")

# ── 4. Cathedral markers ──
print("  Adding cathedrals...")
cath_fg = folium.FeatureGroup(name='Cathedrals')
for diocese, cath_list in cathedrals.items():
    color = color_map.get(diocese, '#ffffff')
    is_arch = diocese in archdioceses
    for i, (lat, lon, name) in enumerate(cath_list):
        folium.CircleMarker(
            location=[lat, lon], radius=6 if i == 0 else 4,
            color=RED if is_arch else 'white',
            fill=True, fillColor=color, fillOpacity=1,
            weight=3 if is_arch else 2,
            popup=f'<b>{diocese}</b><br>{name}',
            tooltip=diocese
        ).add_to(cath_fg)
cath_fg.add_to(m)

# ── Layer control ──
folium.LayerControl(collapsed=True).add_to(m)

output = 'us_diocese_star_map.html'
m.save(output)
print(f"\nSaved: {output} ({os.path.getsize(output)/1024/1024:.1f} MB)")
print(f"  {len(archdioceses)} archdioceses with red borders")

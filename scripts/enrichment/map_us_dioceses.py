"""
Generate a color-coded interactive map of US Catholic dioceses.
Uses Burchfiel's diocese_boundaries_revised.geojson (hand-edited boundaries).
"""
import geopandas as gpd
import folium
from scripts.visualization.map_utils import folium_default_layers
import branca
import numpy as np

# Load revised diocese boundaries
print("Loading diocese boundaries...")
dioceses = gpd.read_file('data/diocese_mapper/diocese_boundaries_revised.geojson')
print(f"  {len(dioceses)} dioceses loaded")

# Sort alphabetically for consistent coloring
dioceses = dioceses.sort_values('Diocese').reset_index(drop=True)

# Assign 12 distinct colors (same as Burchfiel's approach)
n_dioceses = len(dioceses)
dioceses['color_idx'] = np.arange(n_dioceses) % 12

# Create colormap
colormap = branca.colormap.linear.Paired_12.scale(0, 11)
colormap.caption = 'US Catholic Dioceses'

# Create base map centered on US
m = folium.Map(location=[39.8, -98.5], zoom_start=5, tiles=None, control_scale=True)
folium_default_layers(m)

# Color function
def style_function(feature):
    idx = feature['properties'].get('color_idx', 0) % 12
    return {
        'fillColor': colormap(idx),
        'color': '#555555',
        'weight': 1,
        'fillOpacity': 0.7
    }

# Add diocese polygons
folium.GeoJson(
    dioceses,
    style_function=style_function,
    tooltip=folium.GeoJsonTooltip(
        fields=['Diocese'],
        aliases=['Diocese:']
    )
).add_to(m)

# Add province boundaries (black lines)
try:
    provinces = gpd.read_file('data/diocese_mapper/province_boundaries_revised.geojson')
    folium.GeoJson(
        provinces,
        style_function=lambda x: {'color': '#000000', 'weight': 2, 'fillOpacity': 0}
    ).add_to(m)
    print("  Province boundaries added")
except Exception as e:
    print(f"  No province boundaries: {e}")

# Add layer control
folium.LayerControl().add_to(m)

# Save
output = 'us_catholic_dioceses_map.html'
m.save(output)
print(f"\nMap saved to: {output}")
print(f"Dioceses mapped: {n_dioceses}")

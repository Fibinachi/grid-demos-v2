"""Extract Admin 1 centroids from Natural Earth shapefile for geocoding fallback."""
import shapefile, os, json

SHP = r"e:\grid\data\natural_earth\ne_10m_admin_1_states_provinces.shp"
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(BASE, 'outputs', 'geocoding', 'admin1_centroids.json')

sf = shapefile.Reader(SHP)
fields = [f[0] for f in sf.fields[1:]]
records = sf.records()

# Key: (name_lower, country_iso) → (lat, lon, full_name)
# Also: (iso_3166_2) → (lat, lon, name)  e.g., "US-CA"
centroids = {}

for r in records:
    name = r[fields.index("name")] or ""
    admin = r[fields.index("admin")] or ""  # country name
    iso_a2 = r[fields.index("iso_a2")] or ""
    iso_3166 = r[fields.index("iso_3166_2")] or ""
    lat = r[fields.index("latitude")] or 0
    lon = r[fields.index("longitude")] or 0
    fips = r[fields.index("fips")] or ""
    
    if not lat or not lon:
        continue
    
    lat, lon = float(lat), float(lon)
    
    # By (name, iso_a2) — for "California, US"
    key1 = (name.strip().lower(), iso_a2.strip().upper())
    if key1 not in centroids:
        centroids[f"{key1[0]}|{key1[1]}"] = (lat, lon, name.strip())
    
    # By iso_3166_2 — for "US-CA"
    if iso_3166:
        centroids[f"CODE:{iso_3166}"] = (lat, lon, name.strip())
    
    # By (fips, US) — for US FIPS codes
    if fips and iso_a2 == "US":
        centroids[f"FIPS:{fips}"] = (lat, lon, name.strip())

with open(OUT, 'w') as f:
    json.dump(centroids, f)

print(f"Extracted {len(centroids):,} admin1 centroid keys")
print(f"Saved to: {OUT}")

# Show some examples
examples = ['california|US', 'CODE:US-CA', 'CODE:CA-ON', 'CODE:IN-MH', 'bavaria|DE']
for ex in examples:
    if ex in centroids:
        lat, lon, name = centroids[ex]
        print(f"  {ex:30s} → {lat:.3f},{lon:.3f} ({name})")

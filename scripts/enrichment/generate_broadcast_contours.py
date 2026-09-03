"""Generate broadcast coverage contours for church-linked broadcasters as GeoJSON."""
import sqlite3, json, math, pandas as pd

DB = "E:/grid/churches.db"
RADIUS_KM = 20  # Conservative default for religious FM/NCE stations
POINTS = 48     # Polygon smoothness

def circle_geojson(lat, lon, radius_km, name):
    coords = []
    for i in range(POINTS):
        angle = 2 * math.pi * i / POINTS
        dlat = (radius_km / 111.32) * math.cos(angle)
        dlon = (radius_km / (111.32 * math.cos(math.radians(lat)))) * math.sin(angle)
        coords.append([lon + dlon, lat + dlat])
    coords.append(coords[0])
    
    return {
        "type": "Feature",
        "properties": {"name": name, "radius_km": radius_km},
        "geometry": {"type": "Polygon", "coordinates": [coords]}
    }

# Get 53 co-located broadcasters with their church pair
db = sqlite3.connect(DB)

df_b = pd.DataFrame(db.execute("""
    SELECT id, name, round(latitude,4) as rlat, round(longitude,4) as rlon,
           latitude, longitude
    FROM churches WHERE is_broadcaster=1 AND latitude IS NOT NULL
""").fetchall(), columns=["id","name","rlat","rlon","lat","lon"])

df_c = pd.DataFrame(db.execute("""
    SELECT id, name, denomination, round(latitude,4) as rlat, round(longitude,4) as rlon
    FROM churches WHERE is_broadcaster=0 AND source!='irs' AND latitude IS NOT NULL
    LIMIT 500000
""").fetchall(), columns=["id","cname","denom","rlat","rlon"])

df_b.to_sql("_b2_temp", db, if_exists="replace", index=False)
df_c.to_sql("_c2_temp", db, if_exists="replace", index=False)
db.execute("CREATE INDEX idx_b2 ON _b2_temp(rlat, rlon)")
db.execute("CREATE INDEX idx_c2 ON _c2_temp(rlat, rlon)")

matches = db.execute("""
    SELECT b.name as broadcaster, b.lat, b.lon, c.cname as church, c.denom
    FROM _b2_temp b
    JOIN _c2_temp c ON b.rlat=c.rlat AND b.rlon=c.rlon
    GROUP BY b.id
""").fetchall()

db.execute("DROP TABLE _b2_temp")
db.execute("DROP TABLE _c2_temp")
db.close()

print(f"Generating contours for {len(matches)} church-linked broadcasters")

# Generate GeoJSON
features = []
for name, lat, lon, church, denom in matches:
    features.append(circle_geojson(lat, lon, RADIUS_KM, f"{name} | {church} ({denom})"))

geojson = {
    "type": "FeatureCollection",
    "properties": {
        "description": "Approximate broadcast coverage contours (20km radius)",
        "source": "church-linked broadcasters (NTEE codes A32-A34, X82-X84)",
        "count": len(features),
        "radius_km": RADIUS_KM
    },
    "features": features
}

out_path = "E:/grid/data/fcc/church_broadcast_contours.geojson"
with open(out_path, "w") as f:
    json.dump(geojson, f)

import os
size = os.path.getsize(out_path)
print(f"Saved: {out_path} ({size:,} bytes, {len(features)} features)")
print(f"Preview: {len(features)} broadcasters, each with {RADIUS_KM}km radius circle")

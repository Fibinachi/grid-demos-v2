"""
Step 3: Compute church-vs-tract elevation diff and generate flood risk map.
Uses existing tract_elevation (13,200 tracts) from our partial Copernicus + Open-Meteo fetch.
Joins: churches → church_districts(TRACT) → tract_elevation → fema_nri_tract
"""
import sqlite3, json
from datetime import datetime

db = sqlite3.connect('churches.db')

print("=== COMPUTING CHURCH VS TRACT ELEVATION DIFFS ===\n")

# Count what's available
tract_el = db.execute("SELECT COUNT(*) FROM tract_elevation").fetchone()[0]
print(f"Tract elevations available: {tract_el:,}")

# Join churches → tracts → tract_elevation → FEMA flood risk
result = db.execute("""
    SELECT 
        c.id, c.name, c.city, c.state, c.latitude, c.longitude,
        te.elevation_m as tract_el,
        f.IFLD_RISKS as inland_flood,
        f.CFLD_RISKS as coastal_flood,
        f.RISK_SCORE as overall_risk,
        f.RISK_RATNG as risk_rating,
        f.STATE, f.COUNTY,
        f.HRCN_RISKS as hurricane_risk,
        f.TRND_RISKS as tornado_risk
    FROM churches c
    JOIN church_districts cd ON c.id = cd.church_id AND cd.layer_code = 'TRACT'
    JOIN tract_elevation te ON cd.geo_id = te.tract_fips
    JOIN fema_nri_tract f ON cd.geo_id = f.TRACTFIPS
    WHERE c.country = 'US'
    AND c.latitude IS NOT NULL
    AND f.IFLD_RISKS > 50  -- moderate to high flood risk
    LIMIT 100
""").fetchall()

print(f"Sample churches in flood zones with tract elevations: {len(result)}")
print()

# Compute diffs for sampled results
print("=== TOP 20 CHURCHES IN FLOOD ZONES (ranked by tract elevation) ===\n")
print(f"{'Church':50s} {'City':20s} {'St':4s} {'Tract El':>8s} {'Flood':>6s} {'Risk':>12s}")
print("-" * 115)

for r in sorted(result, key=lambda x: x[6] or 0, reverse=True)[:20]:
    name = (r[1] or 'Unknown')[:48]
    city = (r[2] or '')[:18]
    state = (r[3] or '')[:4]
    t_el = f"{r[6]:.0f}m" if r[6] else "N/A"
    flood = f"{r[7]:.0f}" if r[7] else "N/A"
    risk = str(r[9] or '')[:12]
    print(f"{name:50s} {city:20s} {state:4s} {t_el:>8s} {flood:>6s} {risk:>12s}")

# Count: how many churches do we have full data for?
full = db.execute("""
    SELECT COUNT(*) FROM churches c
    JOIN church_districts cd ON c.id = cd.church_id AND cd.layer_code = 'TRACT'
    JOIN tract_elevation te ON cd.geo_id = te.tract_fips
    JOIN fema_nri_tract f ON cd.geo_id = f.TRACTFIPS
    WHERE c.country = 'US' AND c.latitude IS NOT NULL
""").fetchone()[0]
print(f"\nChurches with full data (tract el + FEMA): {full:,}")

# High flood (>80) churches
high_flood = db.execute("""
    SELECT COUNT(*) FROM churches c
    JOIN church_districts cd ON c.id = cd.church_id AND cd.layer_code = 'TRACT'
    JOIN tract_elevation te ON cd.geo_id = te.tract_fips
    JOIN fema_nri_tract f ON cd.geo_id = f.TRACTFIPS
    WHERE c.country = 'US' AND c.latitude IS NOT NULL
    AND f.IFLD_RISKS > 80
""").fetchone()[0]
print(f"  Of which are in HIGH inland flood zones (IFLD>80): {high_flood:,}")

# Tract elevation range
el_range = db.execute("SELECT MIN(elevation_m), MAX(elevation_m), AVG(elevation_m) FROM tract_elevation").fetchone()
print(f"\nTract elevation range: {el_range[0]:.0f}m - {el_range[1]:.0f}m (avg {el_range[2]:.0f}m)")

# Generate map data
print("\n=== GENERATING MAP DATA ===")
map_data = db.execute("""
    SELECT 
        c.id, c.name, c.latitude, c.longitude,
        te.elevation_m as tract_elevation_m,
        f.IFLD_RISKS, f.CFLD_RISKS, f.RISK_SCORE, f.RISK_RATNG,
        f.STATE, f.COUNTY
    FROM churches c
    JOIN church_districts cd ON c.id = cd.church_id AND cd.layer_code = 'TRACT'
    JOIN tract_elevation te ON cd.geo_id = te.tract_fips
    JOIN fema_nri_tract f ON cd.geo_id = f.TRACTFIPS
    WHERE c.country = 'US' AND c.latitude IS NOT NULL
    AND f.IFLD_RISKS > 50
    ORDER BY te.elevation_m DESC
""").fetchall()

print(f"Map data: {len(map_data):,} churches in moderate+ flood zones")

# Save as JSON for Plotly map
output = []
for r in map_data:
    output.append({
        'id': r[0],
        'name': r[1],
        'lat': r[2],
        'lon': r[3],
        'tract_el': r[4],
        'inland_flood': r[5],
        'coastal_flood': r[6],
        'risk_score': r[7],
        'risk_rating': r[8],
        'state': r[9],
        'county': r[10]
    })

with open('outputs/flood_elevation_map.json', 'w') as f:
    json.dump(output, f)

print(f"Saved {len(output):,} records to outputs/flood_elevation_map.json")

db.close()
print("\nDone! Ready for Step 4 (interactive map).")

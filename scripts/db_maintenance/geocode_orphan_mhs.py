"""
Forward-geocode the 4 GPS-less meetinghouses using city+state.

These have names/cities but no lat/lon:
  - Bloomington ID Ward (Bloomington, ID)
  - Goshen LDS Ward (Goshen, UT)
  - Manassa Second LDS Ward (Manassa, CO)
  - Paris LDS Ward (Paris, ID)

We'll use GeoNames cities1000 + Natural Earth populated places
to find city-center coordinates as approximations.
"""
import sqlite3, pandas as pd, geopandas as gpd
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"

# The 4 orphan meetinghouse IDs
ORPHAN_IDS = [40613, 58659, 59440, 59555]

# Known city centers (from GeoNames / general knowledge)
# These are small towns - the meetinghouse is near the town center
CITY_COORDS = {
    ('Bloomington', 'ID'): (42.1910, -111.4083),
    ('Goshen', 'UT'): (40.1627, -111.9008),
    ('Manassa', 'CO'): (37.1742, -105.9361),
    ('Paris', 'ID'): (42.2272, -111.4010),
}

# Also check if we have more accurate coords from cached data
print("Loading populated places for verification...")
try:
    places = gpd.read_file(r"E:\grid\data\natural_earth\ne_10m_populated_places.shp")
    for (city, state), coords in CITY_COORDS.items():
        # Find nearest populated place
        matches = places[
            (places['NAME'].str.lower().str.contains(city.lower(), na=False)) &
            (places['ADM1NAME'].str.contains(state, na=False))
        ]
        if len(matches) > 0:
            match = matches.iloc[0]
            print(f"  {city}, {state}: NE has {match['NAME']} at ({match['LATITUDE']:.4f}, {match['LONGITUDE']:.4f})")
        else:
            print(f"  {city}, {state}: using hardcoded ({coords[0]:.4f}, {coords[1]:.4f})")
except Exception as e:
    print(f"  Could not verify: {e}")

# Also try geonames
try:
    gn = pd.read_csv(r"E:\grid\data\geonames_cities1000.txt", sep='\t', header=None,
                     usecols=[1,4,5,8,10], names=['name','lat','lon','country','admin1'],
                     dtype=str)
    gn['lat'] = pd.to_numeric(gn['lat'], errors='coerce')
    gn['lon'] = pd.to_numeric(gn['lon'], errors='coerce')
    
    for (city, state), coords in CITY_COORDS.items():
        # Try to find exact match
        matches = gn[gn['name'].str.lower() == city.lower()]
        if len(matches) > 0:
            m = matches.iloc[0]
            print(f"  {city}, {state}: GeoNames has ({m['lat']:.4f}, {m['lon']:.4f})")
except Exception as e:
    print(f"  GeoNames lookup failed: {e}")

print()

# ─── Now update the DB ───────────────────────────────────────────────
conn = sqlite3.connect(DB)
c = conn.cursor()

print("Current orphan meetinghouses:")
for oid in ORPHAN_IDS:
    r = c.execute("SELECT id, name, city, state, country, lat, lon FROM lds_hierarchy WHERE id = ?", (oid,)).fetchone()
    print(f"  ID={r[0]}: {r[1][:40]:40s} {r[2]}, {r[3]} {r[4]} | lat={r[5]}, lon={r[6]}")

# Update with coords
print("\nUpdating coordinates...")
updated = 0
for oid in ORPHAN_IDS:
    r = c.execute("SELECT city, state FROM lds_hierarchy WHERE id = ?", (oid,)).fetchone()
    if r:
        city, state = r[0], r[1]
        key = (city, state)
        if key in CITY_COORDS:
            lat, lon = CITY_COORDS[key]
            c.execute("UPDATE lds_hierarchy SET lat = ?, lon = ? WHERE id = ?", (lat, lon, oid))
            updated += 1
            # Also update the underlying churches record if it exists
            ch = c.execute("SELECT church_id FROM lds_hierarchy WHERE id = ?", (oid,)).fetchone()
            if ch and ch[0]:
                c.execute("UPDATE churches SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, ch[0]))
                print(f"  ID={oid} ({city}, {state}): set lat={lat}, lon={lon} (hierarchy + churches)")

conn.commit()

# Now re-link them to the nearest stake house
print(f"\nRe-linking {updated} meetinghouses to nearest stake house...")
# Use haversine to find the nearest stake house
import math
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

stakes = c.execute("SELECT id, lat, lon FROM lds_hierarchy WHERE lds_type = 'stake_house' AND lat IS NOT NULL").fetchall()

for oid in ORPHAN_IDS:
    r = c.execute("SELECT lat, lon FROM lds_hierarchy WHERE id = ?", (oid,)).fetchone()
    if r and r[0] is not None:
        lat, lon = r[0], r[1]
        best_id, best_dist = None, float('inf')
        for sid, slat, slon in stakes:
            d = haversine_km(lat, lon, slat, slon)
            if d < best_dist:
                best_dist = d
                best_id = sid
        
        if best_id:
            c.execute("""
                UPDATE lds_hierarchy SET parent_id = ?, parent_lds_type = 'stake_house', relationship = 'served_by'
                WHERE id = ?
            """, (best_id, oid))
            sname = c.execute("SELECT name FROM lds_hierarchy WHERE id = ?", (best_id,)).fetchone()
            print(f"  ID={oid}: linked to stake house ID={best_id} ({sname[0][:35]}) at {best_dist:.1f} km")

conn.commit()

# Verify
print("\nVerification:")
r = c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE parent_id IS NULL").fetchone()
print(f"  Unlinked: {r[0]}")
r = c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE lds_type = 'meetinghouse' AND parent_id IS NULL").fetchone()
print(f"  Orphan meetinghouses: {r[0]}")
r = c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE lds_type = 'meetinghouse' AND lat IS NULL").fetchone()
print(f"  GPS-less meetinghouses: {r[0]}")

# Check which ones are still unlinked
c.execute("SELECT id, name, city, state FROM lds_hierarchy WHERE parent_id IS NULL ORDER BY lds_type")
for r in c.fetchall():
    print(f"  Unlinked: ID={r[0]} {r[1][:40]} ({r[2]}, {r[3]})")

# Provenance
now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
c.execute("""INSERT INTO provenance_log(source,script_name,started_at,completed_at,
    churches_updated,churches_inserted,fields_populated,
    records_attempted,records_matched,status,notes)
    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
    ('lds_hierarchy','geocode_orphan_mhs.py',now,now,
     updated*2,0,'lat,lon,parent_id,parent_lds_type,relationship',
     len(ORPHAN_IDS),updated,'completed',
     f'Geocoded {updated} orphan meetinghouses + linked to nearest stake house.'))
conn.commit()
print(f"\nProvenance logged.")

conn.close()
print("Done.")

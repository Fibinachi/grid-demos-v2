"""Geocode CA via pgeocode FSA lookup — single update SQL."""
import sqlite3, pgeocode
from datetime import datetime, timezone
from collections import defaultdict

NOW = datetime.now(timezone.utc).isoformat()
DB = "E:/grid/churches.db"

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=60000")
c = conn.cursor()

ca_geo = pgeocode.Nominatim('ca')

# Build FSA → (lat, lon) map
c.execute("""SELECT DISTINCT SUBSTR(TRIM(UPPER(REPLACE(zip,' ',''))),1,3) as fsa FROM churches 
    WHERE country='CA' AND latitude IS NULL AND zip IS NOT NULL AND zip != '' AND LENGTH(TRIM(zip)) >= 3""")
fsas = [r[0] for r in c.fetchall() if r[0]]
print(f"Unique FSAs: {len(fsas)}")

fsa_coords = {}
for fsa in fsas:
    r = ca_geo.query_postal_code(fsa)
    if r.latitude and not (r.latitude != r.latitude):
        fsa_coords[fsa] = (r.latitude, r.longitude)
print(f"FSAs with coords: {len(fsa_coords)}")

# Update using CASE expression — single SQL statement
print("Updating churches...")
cases_lat = []
cases_lon = []
fsa_list = []
for fsa, (lat, lon) in fsa_coords.items():
    cases_lat.append(f"WHEN fsa='{fsa}' THEN {lat}")
    cases_lon.append(f"WHEN fsa='{fsa}' THEN {lon}")
    fsa_list.append(f"'{fsa}'")

fsa_in = ','.join(fsa_list)
lat_case = ' '.join(cases_lat)
lon_case = ' '.join(cases_lon)

sql = f"""
    UPDATE churches SET 
        latitude = CASE SUBSTR(TRIM(UPPER(REPLACE(zip,' ',''))),1,3) {lat_case} END,
        longitude = CASE SUBSTR(TRIM(UPPER(REPLACE(zip,' ',''))),1,3) {lon_case} END,
        geocode_source = 'pgeocode_ca'
    WHERE country='CA' AND latitude IS NULL 
    AND SUBSTR(TRIM(UPPER(REPLACE(zip,' ',''))),1,3) IN ({fsa_in})
"""
try:
    c.execute(sql)
    print(f"  Updated: {c.rowcount:,}")
    conn.commit()
except Exception as e:
    print(f"  ERROR: {e}")

# Link to holy_sites
print("\nLinking to holy_sites...")
c.execute("""UPDATE churches SET holy_site_id = (
    SELECT h.site_id FROM holy_sites h
    WHERE ROUND(h.lat,5)=ROUND(churches.latitude,5) AND ROUND(h.lon,5)=ROUND(churches.longitude,5) LIMIT 1)
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'""")
print(f"  Linked: {c.rowcount:,}")
conn.commit()

# New holy_sites
c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
grid = set(c.fetchall())

c.execute("SELECT id, name, faith, country, latitude, longitude FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='pgeocode_ca'")
new_hs = 0
for ch_id, name, faith, country, lat, lon in c.fetchall():
    gl, gn = round(lat,4), round(lon,4)
    if (gl,gn) not in grid:
        c.execute("INSERT INTO holy_sites(name,faith,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?)",
                 ((name or '')[:500], faith, country, lat, lon, 'pgeocode', 0, 'church', 0.5))
        grid.add((gl,gn))
        c.execute("UPDATE churches SET holy_site_id=? WHERE id=?", (c.lastrowid, ch_id))
        new_hs += 1
conn.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND latitude IS NULL")
still = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND latitude IS NOT NULL")
has = c.fetchone()[0]

print(f"\n=== Results ===")
print(f"  CA with coords: {has:,}")
print(f"  CA without: {still:,}")
print(f"  New holy_sites: {new_hs:,}")

geocoded = has - 31504  # rough calculation
c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
         ("pgeocode","geocode_ca_fsa.py",NOW,datetime.now(timezone.utc).isoformat(),0,"lat,lon,geocode_source,holy_site_id",geocoded,geocoded,f"pgeocode CA FSA: {geocoded:,} geocoded"))
conn.commit()
conn.close()
print("\nDone.")

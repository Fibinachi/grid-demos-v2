"""Test geocoder.ca and build full CA geocoding pipeline."""
import sqlite3, json, urllib.request, urllib.parse, time, csv
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
DB = "E:/grid/churches.db"

def geocode_ca(address, city="", province=""):
    """Geocode Canadian address using geocoder.ca. Returns (lat, lon, postal) or (None,None,None)."""
    if not address or not address.strip():
        return None, None, None
    
    # Clean address
    addr = address.encode('ascii', errors='replace').decode('ascii').replace('?',' ').strip()[:200]
    if not addr:
        return None, None, None
    
    # Build query with city/province
    full = addr
    if city and city not in addr:
        full += f", {city}"
    if province and province not in full:
        full += f", {province}"
    
    # geocoder.ca API
    params = {
        "locate": full,
        "geoit": "xml",  # CSV output
        "json": 1,
    }
    
    try:
        url = "https://geocoder.ca/?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        
        lat = data.get("latt", "") or data.get("lat", "")
        lon = data.get("longt", "") or data.get("lng", "")
        
        if lat and lon:
            return float(lat), float(lon), data.get("postal", "")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(5)
    except:
        pass
    
    return None, None, None

# ── Quick test ──
print("Testing geocoder.ca...")
lat, lon, postal = geocode_ca("150 Southwell Rd", "Columbia", "SC")
print(f"  150 Southwell Rd, Columbia, SC: lat={lat}, lon={lon}")

lat, lon, postal = geocode_ca("77 Sherman Street", "Hartford", "CT")
print(f"  77 Sherman Street, Hartford, CT: lat={lat}, lon={lon}")

# Test a real CA address from DB
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("""SELECT address, city, state FROM churches 
    WHERE country='CA' AND address IS NOT NULL AND address != '' 
    AND latitude IS NULL LIMIT 3""")
for addr, city, state in c.fetchall():
    if addr:
        lat, lon, _ = geocode_ca(addr, city, state)
        print(f"  {addr[:60]}: lat={lat}, lon={lon}")

# ── Full pipeline ──
c.execute("""SELECT COUNT(*) FROM churches 
    WHERE country='CA' AND address IS NOT NULL AND address != '' AND latitude IS NULL""")
total = c.fetchone()[0]
print(f"\nCA entries needing geocode: {total:,}")

if total == 0:
    conn.close()
    exit()

c.execute("""SELECT id, address, city, state FROM churches 
    WHERE country='CA' AND address IS NOT NULL AND address != '' AND latitude IS NULL
    ORDER BY id""")
rows = c.fetchall()

print(f"Starting geocoding of {len(rows):,} CA entries...")
geocoded = 0
batch = []

for i, (ch_id, address, city, state) in enumerate(rows):
    lat, lon, postal = geocode_ca(address, city, state)
    
    if lat and lon:
        batch.append((lat, lon, ch_id))
        geocoded += 1
    
    if len(batch) >= 50:
        c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='geocoder_ca' WHERE id=?", batch)
        conn.commit()
        batch = []
    
    if (i+1) % 500 == 0:
        print(f"  {i+1:,}/{len(rows):,} — {geocoded:,} geocoded ({geocoded*100//(i+1)}%)")
    
    time.sleep(0.2)  # 5 req/sec

if batch:
    c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='geocoder_ca' WHERE id=?", batch)
    conn.commit()

# ── Link to holy_sites ──
print("\nLinking to holy_sites...")
c.execute("""UPDATE churches SET holy_site_id = (
    SELECT h.site_id FROM holy_sites h
    WHERE ROUND(h.lat,5) = ROUND(churches.latitude,5)
      AND ROUND(h.lon,5) = ROUND(churches.longitude,5) LIMIT 1)
    WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='geocoder_ca'""")

c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
grid = set(c.fetchall())

c.execute("SELECT id, name, faith, denomination, country, latitude, longitude, source FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='geocoder_ca'")
new_hs = 0
for row in c.fetchall():
    ch_id, name, faith, denom, country, lat, lon, source = row
    gl, gn = round(lat,4), round(lon,4)
    if (gl,gn) not in grid:
        c.execute("INSERT INTO holy_sites(name,faith,tradition,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
                 ((name or '')[:500], faith, denom, country, lat, lon, source or 'geocoder_ca', 0, 'church', 0.7))
        grid.add((gl,gn))
        c.execute("UPDATE churches SET holy_site_id=? WHERE id=?", (c.lastrowid, ch_id))
        new_hs += 1

conn.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND latitude IS NULL")
still = c.fetchone()[0]
print(f"\n=== Results ===")
print(f"  Geocoded: {geocoded:,}")
print(f"  New holy_sites: {new_hs:,}")
print(f"  Still ungeocoded CA: {still:,}")

c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
         ("geocoder_ca","geocode_ca.py",NOW,datetime.now(timezone.utc).isoformat(),0,"lat,lon,geocode_source,holy_site_id",len(rows),geocoded,f"geocoder.ca: {geocoded:,}/{len(rows):,}"))
conn.commit()
conn.close()
print("\nDone.")

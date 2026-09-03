"""Geocode CA churches — city centroids for PO boxes, Nominatim for streets."""
import sqlite3, json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
DB = "E:/grid/churches.db"

def geocode_nominatim(address, country="CA"):
    """Free Nominatim geocode. Returns (lat, lon)."""
    if not address or not address.strip():
        return None, None
    addr = address.encode('ascii', errors='replace').decode('ascii').replace('?',' ').strip()[:200]
    if not addr or addr.upper().startswith('PO BOX') or addr.upper().startswith('BOX '):
        return None, None
    
    params = {"q": addr, "format": "json", "limit": 1, "countrycodes": country}
    try:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0 (grantwizard@example.com)"})
        data = json.loads(urllib.request.urlopen(req, timeout=5).read())
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None, None

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND address IS NOT NULL AND address != '' AND latitude IS NULL")
    total = c.fetchone()[0]
    print(f"CA entries needing geocode: {total:,}")
    
    # Check how many are PO boxes
    c.execute("""SELECT COUNT(*) FROM churches WHERE country='CA' 
        AND address IS NOT NULL AND address != '' AND latitude IS NULL
        AND (UPPER(address) LIKE 'PO BOX%' OR UPPER(address) LIKE 'BOX %' OR UPPER(address) LIKE 'P.O.%')""")
    po_boxes = c.fetchone()[0]
    print(f"  PO Boxes: {po_boxes:,} (will use city centroids)")
    print(f"  Street addresses: {total - po_boxes:,} (will geocode)")
    
    # ── Pass 1: Geocode street addresses with Nominatim ──
    c.execute("""SELECT id, address, city, state FROM churches 
        WHERE country='CA' AND address IS NOT NULL AND address != '' AND latitude IS NULL
        AND UPPER(address) NOT LIKE 'PO BOX%' AND UPPER(address) NOT LIKE 'BOX %' AND UPPER(address) NOT LIKE 'P.O.%'
        ORDER BY id""")
    street_rows = c.fetchall()
    print(f"\nPass 1: Geocoding {len(street_rows):,} street addresses...")
    
    geocoded = 0
    batch = []
    
    for i, (ch_id, address, city, state) in enumerate(street_rows):
        full = address
        if city and city not in address:
            full += f", {city}"
        if state and state not in full:
            full += f", {state}"
        full += ", Canada"
        
        lat, lon = geocode_nominatim(full)
        
        if lat and lon:
            batch.append((lat, lon, ch_id))
            geocoded += 1
        
        if len(batch) >= 20:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='nominatim' WHERE id=?", batch)
            conn.commit()
            batch = []
        
        if (i+1) % 100 == 0:
            print(f"  {i+1:,}/{len(street_rows):,} — {geocoded:,} geocoded")
        
        time.sleep(0.1)  # 10 req/sec for street addresses
    
    if batch:
        c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='nominatim' WHERE id=?", batch)
        conn.commit()
    
    print(f"  Street geocode done: {geocoded:,}")
    
    # ── Pass 2: City centroids for PO boxes ──
    c.execute("""SELECT DISTINCT city, state FROM churches 
        WHERE country='CA' AND latitude IS NULL AND address IS NOT NULL
        AND (UPPER(address) LIKE 'PO BOX%' OR UPPER(address) LIKE 'BOX %' OR UPPER(address) LIKE 'P.O.%')
        AND city IS NOT NULL AND city != ''""")
    city_states = [(r[0], r[1]) for r in c.fetchall()]
    print(f"\nPass 2: Getting centroids for {len(city_states):,} unique cities...")
    
    city_coords = {}
    for city, state in city_states:
        if not city:
            continue
        query = f"{city}, {state}, Canada" if state else f"{city}, Canada"
        lat, lon = geocode_nominatim(query)
        if lat and lon:
            city_coords[(city, state)] = (lat, lon)
            print(f"  {city}, {state}: {lat:.4f}, {lon:.4f}")
        time.sleep(0.5)  # Slower for city lookups
    
    # Apply city centroids
    c.execute("""SELECT id, city, state FROM churches 
        WHERE country='CA' AND latitude IS NULL AND address IS NOT NULL
        AND (UPPER(address) LIKE 'PO BOX%' OR UPPER(address) LIKE 'BOX %' OR UPPER(address) LIKE 'P.O.%')
        AND city IS NOT NULL AND city != ''""")
    city_batch = []
    city_geocoded = 0
    for ch_id, city, state in c.fetchall():
        coords = city_coords.get((city, state))
        if coords:
            city_batch.append((coords[0], coords[1], ch_id))
            city_geocoded += 1
    
    if city_batch:
        c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='nominatim_city' WHERE id=?", city_batch)
        conn.commit()
    print(f"  City centroids applied: {city_geocoded:,}")
    
    # ── Link to holy_sites ──
    print("\nLinking to holy_sites...")
    c.execute("""UPDATE churches SET holy_site_id = (
        SELECT h.site_id FROM holy_sites h
        WHERE ROUND(h.lat,5) = ROUND(churches.latitude,5)
          AND ROUND(h.lon,5) = ROUND(churches.longitude,5) LIMIT 1)
        WHERE holy_site_id IS NULL AND latitude IS NOT NULL 
        AND geocode_source IN ('nominatim','nominatim_city')""")
    
    c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
    grid = set(c.fetchall())
    
    c.execute("SELECT id, name, faith, denomination, country, latitude, longitude, source FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source IN ('nominatim','nominatim_city')")
    new_hs = 0
    for row in c.fetchall():
        ch_id, name, faith, denom, country, lat, lon, source = row
        gl, gn = round(lat,4), round(lon,4)
        if (gl,gn) not in grid:
            c.execute("INSERT INTO holy_sites(name,faith,tradition,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     ((name or '')[:500], faith, denom, country, lat, lon, source or 'nominatim', 0, 'church', 0.6))
            grid.add((gl,gn))
            c.execute("UPDATE churches SET holy_site_id=? WHERE id=?", (c.lastrowid, ch_id))
            new_hs += 1
    
    conn.commit()
    
    total_geocoded = geocoded + city_geocoded
    c.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND latitude IS NULL")
    still = c.fetchone()[0]
    
    print(f"\n=== Results ===")
    print(f"  Street geocoded: {geocoded:,}")
    print(f"  City centroids: {city_geocoded:,}")
    print(f"  Total geocoded: {total_geocoded:,}")
    print(f"  New holy_sites: {new_hs:,}")
    print(f"  Still ungeocoded CA: {still:,}")
    
    c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
             ("nominatim","geocode_ca_nominatim.py",NOW,datetime.now(timezone.utc).isoformat(),0,"lat,lon,geocode_source,holy_site_id",total,total_geocoded,f"Nominatim CA: {geocoded:,} streets + {city_geocoded:,} cities"))
    conn.commit()
    conn.close()
    print("\nDone.")

main()

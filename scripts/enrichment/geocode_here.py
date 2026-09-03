"""Geocode non-US churches using HERE API. US will use Census API separately."""
import sqlite3, json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
DB = "E:/grid/churches.db"

with open("E:/grid/data/here_api_key.json") as f:
    HERE_KEY = json.load(f).get("here_api_key", "")

def geocode_here(address, country):
    """Returns (lat, lon) or (None, None)."""
    if not address or not address.strip():
        return None, None
    addr = address.encode('ascii', errors='replace').decode('ascii').replace('?',' ').strip()[:200]
    if not addr:
        return None, None
    
    params = {"q": addr, "apiKey": HERE_KEY, "limit": 1}
    if country and country not in ("ZZ",""):
        params["in"] = f"countryCode:{country}"
    
    try:
        url = "https://geocode.search.hereapi.com/v1/geocode?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        items = data.get("items", [])
        if items:
            pos = items[0].get("position", {})
            return pos.get("lat"), pos.get("lng")
    except:
        pass
    return None, None

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    c = conn.cursor()
    
    # Scope
    c.execute("""SELECT country, COUNT(*) FROM churches 
        WHERE latitude IS NULL AND address IS NOT NULL AND address != ''
          AND country != 'US'
        GROUP BY country ORDER BY 2 DESC""")
    print("Non-US entries needing geocode:")
    for country, cnt in c.fetchall():
        print(f"  {country}: {cnt:,}")
    
    # Fetch (prioritize CA, UK, SG)
    c.execute("""SELECT id, address, city, state, country FROM churches 
        WHERE latitude IS NULL AND address IS NOT NULL AND address != ''
          AND country != 'US'
        ORDER BY CASE country WHEN 'CA' THEN 0 WHEN 'UK' THEN 1 WHEN 'SG' THEN 2 ELSE 3 END, id
        LIMIT 25000""")
    rows = c.fetchall()
    print(f"\nGeocoding {len(rows):,} entries with HERE...")
    
    geocoded = 0
    batch = []
    
    for i, (ch_id, address, city, state, country) in enumerate(rows):
        full = address
        if city and city not in address:
            full += f", {city}"
        if state and state not in full:
            full += f", {state}"
        
        lat, lon = geocode_here(full, country)
        
        if lat and lon:
            batch.append((lat, lon, ch_id))
            geocoded += 1
        
        if len(batch) >= 50:
            c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='here' WHERE id=?", batch)
            conn.commit()
            batch = []
        
        if (i+1) % 500 == 0:
            print(f"  {i+1:,}/{len(rows):,} — {geocoded:,} geocoded")
        
        time.sleep(0.25)
    
    if batch:
        c.executemany("UPDATE churches SET latitude=?, longitude=?, geocode_source='here' WHERE id=?", batch)
        conn.commit()
    
    # Link to holy_sites
    print("\nLinking to holy_sites...")
    c.execute("""UPDATE churches SET holy_site_id = (
        SELECT h.site_id FROM holy_sites h
        WHERE ROUND(h.lat,5) = ROUND(churches.latitude,5)
          AND ROUND(h.lon,5) = ROUND(churches.longitude,5) LIMIT 1)
        WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='here'""")
    linked = c.rowcount
    
    # New holy_sites for unmatched
    c.execute("SELECT ROUND(lat,4), ROUND(lon,4) FROM holy_sites WHERE lat IS NOT NULL")
    grid = set(c.fetchall())
    
    c.execute("SELECT id, name, faith, denomination, country, latitude, longitude, source FROM churches WHERE holy_site_id IS NULL AND latitude IS NOT NULL AND geocode_source='here'")
    new_hs = 0
    for row in c.fetchall():
        ch_id, name, faith, denom, country, lat, lon, source = row
        gl, gn = round(lat,4), round(lon,4)
        if (gl,gn) not in grid:
            c.execute("INSERT INTO holy_sites(name,faith,tradition,country,lat,lon,source_primary,is_landmark,landmark_type,confidence_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
                     ((name or '')[:500], faith, denom, country, lat, lon, source or 'here_geocode', 0, 'church', 0.7))
            grid.add((gl,gn))
            c.execute("UPDATE churches SET holy_site_id=? WHERE id=?", (c.lastrowid, ch_id))
            new_hs += 1
    
    conn.commit()
    
    c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL")
    still = c.fetchone()[0]
    print(f"\n=== Results ===")
    print(f"  Geocoded: {geocoded:,}")
    print(f"  Linked to existing: {linked:,}")
    print(f"  New holy_sites: {new_hs:,}")
    print(f"  Still ungeocoded: {still:,}")
    
    c.execute("INSERT INTO provenance_log(source,script_name,started_at,completed_at,churches_inserted,fields_populated,records_attempted,records_matched,status,notes) VALUES(?,?,?,?,?,?,?,?,'completed',?)",
             ("here_geocode","geocode_here.py",NOW,datetime.now(timezone.utc).isoformat(),0,"lat,lon,geocode_source,holy_site_id",len(rows),geocoded,f"HERE geocode non-US: {geocoded:,}/{len(rows):,}"))
    conn.commit()
    conn.close()
    print("\nDone.")

main()

"""Forward geocode US records with addresses but no ZIP5 via Census API."""
import sys, os, json, time, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect
from datetime import datetime

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

db = connect()
cur = db.cursor()

cur.execute("""
    SELECT id, address, city, state, zip, name
    FROM churches
    WHERE country='US' AND (zip5 IS NULL OR zip5='')
      AND address IS NOT NULL AND address != '' AND address != 'None'
    ORDER BY id
""")
rows = cur.fetchall()
print(f"Records to forward geocode: {len(rows):,}")

now = datetime.now().isoformat()
fixed = 0
failed = 0

for i, (cid, addr, old_city, old_state, old_zip, name) in enumerate(rows):
    # Build one-line address
    parts = [addr, old_city or '', old_state or '', old_zip or '']
    clean = ', '.join(p for p in parts if p)
    clean = ' '.join(clean.split())
    
    try:
        params = urllib.parse.urlencode({"address": clean, "benchmark": "2020", "format": "json"})
        req = urllib.request.Request(f"{CENSUS_URL}?{params}", headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        matches = data.get("result", {}).get("addressMatches", [])
        if matches:
            m = matches[0]
            coords = m.get("coordinates", {})
            addr_comp = m.get("addressComponents", {})
            
            new_lat = coords.get("y")
            new_lon = coords.get("x")
            new_zip = addr_comp.get("zip", "")
            new_city = addr_comp.get("city", "")
            new_state = addr_comp.get("state", "")
            
            if new_lat and new_lon:
                cur.execute("""
                    UPDATE churches SET latitude=?, longitude=?, zip5=?,
                    city=CASE WHEN ?!='' THEN ? ELSE city END,
                    state=CASE WHEN ?!='' THEN ? ELSE state END,
                    last_updated=?, geocode_source='census_street'
                    WHERE id=?
                """, (new_lat, new_lon, new_zip[:5] if new_zip else None,
                      new_city, new_city, new_state, new_state, now, cid))
                fixed += 1
            elif new_zip:
                cur.execute("UPDATE churches SET zip5=?, last_updated=? WHERE id=?", 
                          (new_zip[:5], now, cid))
                fixed += 1
            else:
                failed += 1
        else:
            failed += 1
    except Exception:
        failed += 1
    
    if (i + 1) % 100 == 0:
        db.commit()
        print(f"  {i+1:,}/{len(rows):,} — {fixed} fixed, {failed} failed...")
    time.sleep(0.15)

db.commit()
print(f"\nFixed: {fixed:,}  |  Failed: {failed:,}")
cur.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND (zip5 IS NULL OR zip5='')")
print(f"Still no ZIP5: {cur.fetchone()[0]:,}")
db.close()
print("Done.")

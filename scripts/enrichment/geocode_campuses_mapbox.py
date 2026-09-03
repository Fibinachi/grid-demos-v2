"""Geocode Seacoast + NewSpring campuses via Mapbox."""
import sqlite3, json, time, urllib.request, urllib.parse, os
from datetime import datetime

MAPBOX_KEY = os.environ.get('MAPBOX_API_KEY', '')
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')

conn = sqlite3.connect(DB)
c = conn.cursor()

# Get ungeocoded campuses from our scrapers
rows = c.execute("""
    SELECT id, name, city, state, address FROM churches
    WHERE source IN ('seacoast_scraper', 'newspring_scraper')
    AND (latitude IS NULL OR latitude = 0)
""").fetchall()

print(f"Geocoding {len(rows)} campuses via Mapbox...")
now = datetime.utcnow().isoformat()
geocoded = 0

for church_id, name, city, state, addr in rows:
    # Use full address if available, otherwise name+city+state
    query = addr if addr and len(addr) > 10 else f"{name}, {city}, {state}"
    q = urllib.parse.quote(query)
    url = f"https://api.mapbox.com/search/geocode/v6/forward?q={q}&access_token={MAPBOX_KEY}&limit=1"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        
        if data.get('features'):
            feat = data['features'][0]
            coords = feat['geometry']['coordinates']
            props = feat['properties']
            full_addr = props.get('full_address', '')
            
            c.execute("""UPDATE churches SET 
                latitude=?, longitude=?, address=?,
                geocode_source='mapbox', geocode_confidence=0.9, 
                geocode_last_verified=?, geocode_attempts = geocode_attempts + 1
                WHERE id=?""", (coords[1], coords[0], full_addr, now, church_id))
            geocoded += 1
            print(f"  {name[:50]:50s} -> {coords[1]:.5f}, {coords[0]:.5f}")
        else:
            print(f"  {name[:50]:50s} -> NO MATCH")
        
        time.sleep(0.15)  # Rate limit: ~6/sec
        
    except Exception as e:
        print(f"  {name[:50]:50s} -> ERROR: {e}")

conn.commit()
print(f"\nGeocoded: {geocoded}/{len(rows)}")
c.execute("SELECT COUNT(1) FROM churches WHERE source IN ('seacoast_scraper','newspring_scraper') AND latitude IS NOT NULL")
print(f"Now have coordinates for: {c.fetchone()[0]} campuses")
conn.close()

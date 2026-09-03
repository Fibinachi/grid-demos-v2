import sqlite3, json, time, urllib.request, urllib.parse, os
from datetime import datetime

MAPBOX_KEY = os.environ.get('MAPBOX_API_KEY', '')
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
conn = sqlite3.connect('churches.db')
c = conn.cursor()
rows = c.execute("SELECT id, name, city, state FROM churches WHERE source='newspring_scraper'").fetchall()
now = datetime.utcnow().isoformat()
geocoded = 0

for church_id, name, city, state in rows:
    city_name = name.replace('NewSpring Church - ', '').strip()
    query = f'NewSpring Church, {city_name}, {state}'
    q = urllib.parse.quote(query)
    url = f'https://api.mapbox.com/search/geocode/v6/forward?q={q}&access_token={MAPBOX_KEY}&limit=1'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        if data.get('features'):
            feat = data['features'][0]
            coords = feat['geometry']['coordinates']
            addr = feat['properties'].get('full_address','')
            c.execute('UPDATE churches SET latitude=?,longitude=?,address=?,geocode_source=?,geocode_confidence=0.9,geocode_last_verified=?,geocode_attempts=geocode_attempts+1 WHERE id=?', (coords[1],coords[0],addr,'mapbox',now,church_id))
            geocoded += 1
            print(f'  {city_name:25s} -> {coords[1]:.5f},{coords[0]:.5f}')
        else:
            print(f'  {city_name:25s} -> NO MATCH')
    except Exception as e:
        print(f'  {city_name:25s} -> {e}')
    time.sleep(0.15)

conn.commit()
c.execute("SELECT COUNT(1) FROM churches WHERE source='newspring_scraper' AND latitude IS NOT NULL")
print(f"\nNewSpring with coords: {c.fetchone()[0]}/{len(rows)}")
c.execute("SELECT COUNT(1) FROM churches WHERE source='seacoast_scraper' AND latitude IS NOT NULL")
print(f"Seacoast with coords: {c.fetchone()[0]}")
conn.close()

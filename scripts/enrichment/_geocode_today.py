"""Geocode today's scrapes that don't have GPS."""
import sqlite3, requests, time

DB = r'E:\grid\churches.db'

db = sqlite3.connect(DB)
db.execute('PRAGMA busy_timeout=60000')
c = db.cursor()

# Today's sources without GPS
sources = ['pb_directory_import', 'bma_directory', 'clc_directory', 'emc_scrape', 'smc_playwright']

# Get churches needing geocoding (have address, no GPS)
churches = []
for src in sources:
    rows = c.execute("""
        SELECT id, name, address, city, state FROM churches
        WHERE source=? AND latitude IS NULL AND address IS NOT NULL AND address != ''
    """, (src,)).fetchall()
    churches.extend(rows)
    print(f'  {src}: {len(rows)} to geocode')

print(f'\n  Total: {len(churches)} churches to geocode')

# Geocode with Nominatim (1 req/s)
geocoded = 0
failed = 0

for ch in churches:
    ch_id, name, addr, city, state = ch
    query = f"{addr}, {city}, {state}, USA"
    
    try:
        r = requests.get('https://nominatim.openstreetmap.org/search', 
                        params={'q': query, 'format': 'json', 'limit': 1},
                        headers={'User-Agent': 'GRID/1.0'},
                        timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                c.execute("UPDATE churches SET latitude=?, longitude=? WHERE id=?", (lat, lon, ch_id))
                geocoded += 1
            else:
                failed += 1
        else:
            failed += 1
    except Exception:
        failed += 1
    
    if geocoded % 100 == 0:
        db.commit()
        print(f'  {geocoded}/{len(churches)} geocoded...')
    
    time.sleep(1.05)  # Nominatim rate limit

db.commit()
print(f'\n  Geocoded: {geocoded}')
print(f'  Failed: {failed}')
db.close()
print('DONE')

"""
Complete reverse geocoding for ALL churches missing city data.
Uses local WSL Nominatim on port 8088.
8 threads, no rate limit.
"""
import sqlite3, requests, time, sys, os, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'churches.db')
NOMINATIM_URL = 'http://127.0.0.1:8088/reverse'
THREADS = 8
CHUNK = 500

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def build_street(addr):
    parts = []
    hn = addr.get('house_number', '')
    road = addr.get('road', '') or addr.get('pedestrian', '') or addr.get('footway', '') or addr.get('path', '')
    if hn and road: parts.append(f'{hn} {road}')
    elif road: parts.append(road)
    nb = addr.get('neighbourhood', '') or addr.get('suburb', '') or addr.get('quarter', '')
    if nb and nb != road: parts.append(nb)
    return ', '.join(parts) if parts else ''

def extract_city(addr):
    return (addr.get('city') or addr.get('town') or addr.get('village') or
            addr.get('hamlet') or addr.get('municipality') or addr.get('suburb') or addr.get('county'))

def extract_state(addr):
    return (addr.get('state') or addr.get('province') or addr.get('region') or addr.get('state_district'))

def reverse_one(row):
    chid, lat, lon, country, name = row
    try:
        r = requests.get(NOMINATIM_URL, params={
            'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1, 'accept-language': 'en'
        }, timeout=15)
        if r.status_code != 200:
            return ('http_error', chid, r.status_code)
        data = r.json()
        if not data or 'address' not in data:
            return ('no_result', chid)
        addr = data['address']
        city = extract_city(addr)
        if not city:
            return ('no_city', chid)
        state = extract_state(addr)
        postcode = addr.get('postcode', '')
        street = build_street(addr)
        nom_country = addr.get('country', '')
        new_lat = float(data.get('lat', lat))
        new_lon = float(data.get('lon', lon))
        return ('ok', chid, street, city, state, postcode, new_lat, new_lon, nom_country)
    except Exception as e:
        return ('error', chid, str(e)[:80])

# ── Connect ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# Check what needs work
c.execute("SELECT COUNT(*) FROM churches WHERE city IS NOT NULL AND city!=''")
have_city = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches")
total_churches = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL")
need_city = c.fetchone()[0]

print(f"=== Current State ===")
print(f"Total churches: {total_churches:,}")
print(f"Have city: {have_city:,} ({have_city/total_churches*100:.1f}%)")
print(f"Need city: {need_city:,}")
print()

if need_city == 0:
    print("All cities filled! Nothing to do.")
    db.close()
    sys.exit(0)

# ── Fetch rows ──
c.execute("SELECT id, latitude, longitude, country, name FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL ORDER BY id")
rows = c.fetchall()
print(f"Processing {len(rows):,} entries with {THREADS} threads...")
print()

start = time.time()
batch = []
updated = 0
failed = 0
no_result = 0

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = {executor.submit(reverse_one, row): row for row in rows}
    
    for i, future in enumerate(as_completed(futures)):
        result = future.result()
        code = result[0]
        
        if i % 5000 == 0 and i > 0:
            elapsed = time.time() - start
            rate = i / elapsed
            eta = (len(rows) - i) / rate
            print(f"  {i:,}/{len(rows):,} ({i/len(rows)*100:.0f}%) - {rate:.0f} rec/s - ETA {eta/60:.1f}m - updated={updated:,}")
        
        if code == 'ok':
            _, chid, street, city, state, postcode, new_lat, new_lon, nom_country = result
            batch.append((street, city, state, postcode, new_lat, new_lon, nom_country, chid))
            if len(batch) >= CHUNK:
                c.executemany(
                    """UPDATE churches SET 
                       address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                       city=?, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                       zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
                       latitude=?, longitude=?,
                       country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END
                       WHERE id=?""",
                    batch
                )
                db.commit()
                updated += len(batch)
                batch = []
        elif code in ('http_error', 'error'):
            failed += 1
        elif code in ('no_result', 'no_city'):
            no_result += 1

# Flush remaining
if batch:
    c.executemany(
        """UPDATE churches SET 
           address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
           city=?, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
           zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
           latitude=?, longitude=?,
           country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END
           WHERE id=?""",
        batch
    )
    db.commit()
    updated += len(batch)

elapsed = time.time() - start
print()
print(f"{'='*60}")
print(f"COMPLETE: {len(rows):,} in {elapsed:.0f}s ({len(rows)/elapsed:.0f} rec/s)")
print(f"  Updated: {updated:,} | Failed: {failed:,} | No result: {no_result:,}")

# Final count
c.execute("SELECT COUNT(*) FROM churches WHERE city IS NOT NULL AND city!=''")
final_have = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL")
final_need = c.fetchone()[0]
print(f"  Before: {have_city:,} with city -> After: {final_have:,} with city")
print(f"  Still need city: {final_need:,}")
db.close()

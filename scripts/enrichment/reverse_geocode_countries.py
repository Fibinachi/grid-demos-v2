"""
Reverse-geocode churches in specific countries using Nominatim public API.
FILLS: address (street), city, state, zip, country (if blank)
CORRECTS: latitude/longitude -> snapped to Nominatim centroid

Rate limit: 1 req/s (Nominatim public policy). Polite: 1.1s between requests.

Usage:
  python scripts/enrichment/reverse_geocode_countries.py              # all non-US
  python scripts/enrichment/reverse_geocode_countries.py --countries CA,GB       # specific
  python scripts/enrichment/reverse_geocode_countries.py --dry-run    # test 5 samples
  python scripts/enrichment/reverse_geocode_countries.py --limit 100
  python scripts/enrichment/reverse_geocode_countries.py --local      # use local Docker
"""
import sqlite3, requests, time, sys, os, math, random
from datetime import datetime, timezone
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
UA = f'GRID/1.0 (https://github.com/GRID-project; academic research) run-{random.randint(1000,9999)}'

# ── CLI Args ──
DRY_RUN = '--dry-run' in sys.argv
NO_SNAP = '--no-snap' in sys.argv
USE_LOCAL = '--local' in sys.argv
LIMIT = None
TARGET_COUNTRIES = None

for i, a in enumerate(sys.argv):
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a == '--countries' and i+1 < len(sys.argv):
        TARGET_COUNTRIES = [c.strip().upper() for c in sys.argv[i+1].split(',')]

if USE_LOCAL:
    NOMINATIM_URL = 'http://localhost:8080/reverse'
else:
    NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'

# ── Helpers ──
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
    if hn and road:
        parts.append(f'{hn} {road}')
    elif road:
        parts.append(road)
    nb = addr.get('neighbourhood', '') or addr.get('suburb', '') or addr.get('quarter', '')
    if nb and nb != road:
        parts.append(nb)
    return ', '.join(parts) if parts else ''

def extract_city(addr):
    """Extract and validate city name from Nominatim address dict.
    Returns '' if the value looks scrambled (coordinates, HTML, too long, etc.)."""
    import html, re
    raw = (addr.get('city') or addr.get('town') or addr.get('village') or
           addr.get('hamlet') or addr.get('municipality') or
           addr.get('suburb') or '')
    if not raw:
        return ''
    if re.search(r'&#\d+;|&#x[0-9a-f]+;|&lt;|&gt;|&amp;|&quot;', raw):
        return ''
    try:
        raw = html.unescape(raw)
    except Exception:
        pass
    raw = raw.strip()
    if not raw:
        return ''
    if re.search(r'[\u00b0\u2032\u2033]', raw):
        return ''
    if re.search(r'\d+\.\d+[\u00b0]', raw):
        return ''
    if len(raw) > 80:
        return ''
    if raw.count(',') >= 3:
        return ''
    if re.search(r'\b(is one|is a|located in|directly subject|under the)\b', raw, re.IGNORECASE):
        return ''
    return raw

def extract_state(addr):
    return (addr.get('state') or addr.get('province') or
            addr.get('region') or addr.get('state_district'))

# ── Connect ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# ── Build query ──
if TARGET_COUNTRIES:
    country_filter = "AND c.country IN (" + ",".join(f"'{x}'" for x in TARGET_COUNTRIES) + ")"
    mode_label = f"countries: {','.join(TARGET_COUNTRIES)}"
else:
    country_filter = "AND c.country != 'US'"
    mode_label = "all non-US"

# Get records that are geocoded but missing any address field (address, city, state, zip)
sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name,
    c.address, c.city, c.state, c.zip
FROM churches c
WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
  {country_filter}
  AND (
    (c.address IS NULL OR c.address = '') OR
    (c.city IS NULL OR c.city = '') OR
    (c.state IS NULL OR c.state = '') OR
    (c.zip IS NULL OR c.zip = '')
  )
ORDER BY c.id"""

if LIMIT:
    sql += f' LIMIT {LIMIT}'

c.execute(sql)
rows = c.fetchall()
total = len(rows)
rate = "unlimited" if USE_LOCAL else "1 req/s"
print(f"Mode: {mode_label}")
print(f"API: {'LOCAL Docker' if USE_LOCAL else 'PUBLIC nominatim.openstreetmap.org'}")
print(f"Records: {total:,}")
print(f"Snap coords: {'OFF' if NO_SNAP else 'ON'} | Dry run: {'YES' if DRY_RUN else 'NO'}")
if not USE_LOCAL:
    print(f"ETA: {total/3600:.1f}h at 1 req/s")
print()

if total == 0:
    print("Nothing to do!")
    db.close()
    sys.exit(0)

# ── Dry Run ──
if DRY_RUN:
    print("DRY RUN — will not write to DB. Sample:")
    session = requests.Session()
    session.headers.update({'User-Agent': UA})
    for row in rows[:5]:
        chid, lat, lon, country, name, addr_existing, city_existing, state_existing, zip_existing = row
        try:
            r = session.get(NOMINATIM_URL, params={
                'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1
            }, timeout=15)
            if r.ok:
                d = r.json()
                addr = d.get('address', {})
                street = build_street(addr)
                city = extract_city(addr)
                state = extract_state(addr)
                zipcode = addr.get('postcode', '')
                new_lat = float(d.get('lat', lat))
                new_lon = float(d.get('lon', lon))
                dist = haversine_km(lat, lon, new_lat, new_lon)
                print(f"  [{chid}] '{name[:50] if name else 'N/A'}' ({country})")
                print(f"       existing: addr='{addr_existing}' city='{city_existing}' state='{state_existing}' zip='{zip_existing}'")
                print(f"       nominatim: street='{street}' city='{city}' state='{state}' zip='{zipcode}'")
                print(f"       old=({lat:.5f},{lon:.5f}) new=({new_lat:.5f},{new_lon:.5f}) snap={dist*1000:.0f}m")
            else:
                print(f"  [{chid}] HTTP {r.status_code}")
        except Exception as e:
            print(f"  [{chid}] Error: {e}")
        time.sleep(0.05)
    print(f"\n  ... and {total - 5:,} more")
    db.close()
    sys.exit(0)

# ── Process ──
session = requests.Session()
session.headers.update({'User-Agent': UA})

CHUNK = 500
batch_updates = []
updated = 0
filled_addr = 0
filled_city = 0
filled_state = 0
filled_zip = 0
snapped = 0
snap_dist_total = 0.0
failed = 0
no_result = 0
start = time.time()

pbar = tqdm(rows, desc="Reverse geocoding", unit='rec')

for row in pbar:
    chid, lat, lon, country, name, addr_existing, city_existing, state_existing, zip_existing = row
    
    try:
        params = {'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1}
        if not USE_LOCAL:
            params['accept-language'] = 'en'
        
        r = session.get(NOMINATIM_URL, params=params, timeout=15)
        
        if r.status_code == 429:
            pbar.write("  Rate limited (429), backing off 30s...")
            time.sleep(30)
            continue
        
        if r.status_code != 200:
            failed += 1
            if failed <= 3:
                pbar.write(f"  HTTP {r.status_code} for id={chid}")
            time.sleep(2 if not USE_LOCAL else 0.1)
            continue
        
        data = r.json()
        if not data or 'address' not in data:
            no_result += 1
            if not USE_LOCAL:
                time.sleep(1.1)
            continue
        
        addr = data['address']
        
        # Extract fields
        street = build_street(addr)
        city = extract_city(addr)
        state = extract_state(addr)
        zipcode = addr.get('postcode', '')
        new_lat = float(data.get('lat', lat))
        new_lon = float(data.get('lon', lon))
        
        # Build update
        sets = []
        params_update = []
        
        if street and (not addr_existing or addr_existing == ''):
            sets.append("address = ?")
            params_update.append(street)
            filled_addr += 1
        
        if city and (not city_existing or city_existing == ''):
            sets.append("city = ?")
            params_update.append(city)
            filled_city += 1
        
        if state and (not state_existing or state_existing == ''):
            sets.append("state = ?")
            params_update.append(state)
            filled_state += 1
        
        if zipcode and (not zip_existing or zip_existing == ''):
            sets.append("zip = ?")
            params_update.append(zipcode)
            filled_zip += 1
        
        if not NO_SNAP:
            dist = haversine_km(lat, lon, new_lat, new_lon)
            if dist > 0.001:  # More than 1 meter
                sets.append("latitude = ?")
                params_update.append(new_lat)
                sets.append("longitude = ?")
                params_update.append(new_lon)
                snapped += 1
                snap_dist_total += dist
        
        if sets:
            sets.append("last_updated = ?")
            params_update.append(NOW)
            params_update.append(chid)
            batch_updates.append((sets, params_update))
        
        if len(batch_updates) >= CHUNK:
            for sets, params_update in batch_updates:
                c.execute(f"UPDATE churches SET {', '.join(sets)} WHERE id = ?", params_update)
            db.commit()
            updated += len(batch_updates)
            batch_updates = []
        
        if not USE_LOCAL:
            time.sleep(1.1)  # Public API rate limit
        
    except Exception as e:
        failed += 1
        if failed <= 5:
            pbar.write(f"  Error for id={chid}: {e}")
        time.sleep(2)
        continue

# Final flush
if batch_updates:
    for sets, params_update in batch_updates:
        c.execute(f"UPDATE churches SET {', '.join(sets)} WHERE id = ?", params_update)
    db.commit()
    updated += len(batch_updates)

# ── Report ──
elapsed = time.time() - start
print(f"\nDone in {elapsed/3600:.1f}h ({elapsed/60:.0f}m)")
print(f"  Updated: {updated:,}")
print(f"  Address filled: {filled_addr:,}")
print(f"  City filled: {filled_city:,}")
print(f"  State filled: {filled_state:,}")
print(f"  Zip filled: {filled_zip:,}")
print(f"  Snapped coords: {snapped:,} (avg {snap_dist_total/snapped*1000:.0f}m)" if snapped else "  Snapped coords: 0")
print(f"  No result: {no_result:,}")
print(f"  Failed: {failed:,}")
if updated > 0:
    print(f"  Rate: {updated/elapsed:.1f} rec/s")

db.close()

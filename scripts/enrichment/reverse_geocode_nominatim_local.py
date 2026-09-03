"""
Reverse-geocode churches using LOCAL Nominatim (WSL on port 8088).
High-throughput: 8 threads, no rate limit.

FILLS: address (street), city, state, zip, country (if blank)
CORRECTS: latitude/longitude -> snapped to Nominatim centroid

Usage:
  python scripts/enrichment/reverse_geocode_nominatim_local.py           # non-US missing city
  python scripts/enrichment/reverse_geocode_nominatim_local.py --us      # US missing address
  python scripts/enrichment/reverse_geocode_nominatim_local.py --all     # ALL missing city (incl US)
  python scripts/enrichment/reverse_geocode_nominatim_local.py --no-address  # ALL missing address (global)
  python scripts/enrichment/reverse_geocode_nominatim_local.py --no-address --states="Texas,California"
  python scripts/enrichment/reverse_geocode_nominatim_local.py --dry-run  # test 5 samples
  python scripts/enrichment/reverse_geocode_nominatim_local.py --limit 100
  python scripts/enrichment/reverse_geocode_nominatim_local.py --no-snap  # don't correct coords
"""
import sqlite3, requests, time, sys, os, math, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'http://127.0.0.1:8088/reverse'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
THREADS = 8  # concurrent workers for local Nominatim

DRY_RUN = '--dry-run' in sys.argv
NO_SNAP = '--no-snap' in sys.argv
US_MODE = '--us' in sys.argv
ALL_MODE = '--all' in sys.argv
NO_ADDR_MODE = '--no-address' in sys.argv
STATES = None
LIMIT = None
for a in sys.argv:
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a.startswith('--states='):
        STATES = [s.strip() for s in a.split('=', 1)[1].split(',') if s.strip()]

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
    # Note: county is deliberately excluded - a county is not a city
    if not raw:
        return ''
    # Check for HTML entities BEFORE unescaping
    if re.search(r'&#\d+;|&#x[0-9a-f]+;|&lt;|&gt;|&amp;|&quot;', raw):
        return ''
    try:
        raw = html.unescape(raw)
    except Exception:
        pass
    raw = raw.strip()
    if not raw:
        return ''
    # Reject coordinate patterns (degree symbol, prime/double-prime)
    if re.search(r'[\u00b0\u2032\u2033]', raw):
        return ''
    if re.search(r'\d+\.\d+[\u00b0]', raw):
        return ''
    # Reject overly long values (not a city name)
    if len(raw) > 80:
        return ''
    # Reject values that look like full addresses (3+ commas)
    if raw.count(',') >= 3:
        return ''
    # Reject values that look like descriptions (containing sentences)
    if re.search(r'\b(is one|is a|located in|directly subject|under the)\b', raw, re.IGNORECASE):
        return ''
    return raw

def extract_state(addr):
    return (addr.get('state') or addr.get('province') or
            addr.get('region') or addr.get('state_district'))

# Coordinate cache — avoid duplicate API calls for same lat/lon
import threading
_coord_cache = {}
_cache_lock = threading.Lock()

def reverse_one(row):
    """Query local Nominatim for one row. Returns tuple for batch UPDATE."""
    chid, lat, lon, country, name = row
    # Round to 4 decimal places (~11m precision) for cache key
    cache_key = (round(lat, 4), round(lon, 4))
    with _cache_lock:
        if cache_key in _coord_cache:
            cached = _coord_cache[cache_key]
            if cached[0] == 'ok':
                _, street, city, state, postcode, new_lat, new_lon, nom_country, dist = cached
                return ('ok', chid, street, city, state, postcode, new_lat, new_lon, nom_country, dist, lat, lon, name, country)
            else:
                return (cached[0], chid, lat, lon, name, country)
    try:
        r = requests.get(NOMINATIM_URL, params={
            'lat': lat, 'lon': lon, 'format': 'json',
            'addressdetails': 1, 'accept-language': 'en'
        }, timeout=15)
        if r.status_code != 200:
            result = ('http_error', chid, r.status_code, lat, lon, name, country)
            _coord_cache[cache_key] = result
            return result
        data = r.json()
        if not data or 'address' not in data:
            result = ('no_result', chid, lat, lon, name, country)
            _coord_cache[cache_key] = result
            return result
        addr = data['address']
        city = extract_city(addr)
        if not city:
            # Try county-level fallback for rural areas, but validate it too
            county = addr.get('county', '')
            if county and len(county) <= 50 and county.count(',') < 2:
                city = county
            else:
                result = ('no_city', chid, lat, lon, name, country)
                _coord_cache[cache_key] = result
                return result
        state = extract_state(addr)
        postcode = addr.get('postcode', '')
        street = build_street(addr)
        nom_country = addr.get('country', '')
        new_lat = float(data.get('lat', lat))
        new_lon = float(data.get('lon', lon))
        dist = haversine_km(lat, lon, new_lat, new_lon) if not NO_SNAP else 0
        if NO_SNAP:
            new_lat, new_lon = lat, lon
        _coord_cache[cache_key] = ('ok', street, city, state, postcode, new_lat, new_lon, nom_country, dist)
        return ('ok', chid, street, city, state, postcode, new_lat, new_lon, nom_country, dist, lat, lon, name, country)
    except Exception as e:
        result = ('error', chid, str(e), lat, lon, name, country)
        _coord_cache[cache_key] = result
        return result

# ── Connect ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# ── Fetch records ──
conditions = []
mode_label = ''

if US_MODE:
    conditions.append("c.country = 'US'")
    conditions.append("c.latitude IS NOT NULL")
    conditions.append("(c.address IS NULL OR c.address = '')")
    mode_label = 'US missing address'
elif NO_ADDR_MODE:
    conditions.append("c.latitude IS NOT NULL")
    conditions.append("(c.address IS NULL OR c.address = '')")
    mode_label = 'ALL missing address'
elif ALL_MODE:
    conditions.append("(c.city IS NULL OR c.city = '')")
    conditions.append("c.latitude IS NOT NULL")
    mode_label = 'ALL missing city'
else:
    conditions.append("(c.city IS NULL OR c.city = '')")
    conditions.append("c.latitude IS NOT NULL")
    conditions.append("c.country != 'US'")
    mode_label = 'non-US missing city'

if STATES:
    placeholders = ','.join(['?' for _ in STATES])
    conditions.append(f"c.state IN ({placeholders})")

order_by = "ORDER BY c.id"
sql = f"SELECT c.id, c.latitude, c.longitude, c.country, c.name FROM churches c WHERE {' AND '.join(conditions)} {order_by}"
if LIMIT:
    sql += f' LIMIT {LIMIT}'

if STATES:
    print(f"Filtering to states: {', '.join(STATES)}")
    c.execute(sql, STATES)
else:
    c.execute(sql)
rows = c.fetchall()
total = len(rows)
print(f"{mode_label}: {total:,}")
print(f"Snap coords: {'OFF' if NO_SNAP else 'ON'} | Dry run: {'YES' if DRY_RUN else 'NO'} | Threads: {THREADS}")
print()

if total == 0:
    print("Nothing to do!")
    db.close()
    sys.exit(0)

if DRY_RUN:
    print("DRY RUN — will not write to DB. Sample:")
    session = requests.Session()
    for chid, lat, lon, country, name in rows[:5]:
        try:
            r = session.get(NOMINATIM_URL, params={
                'lat': lat, 'lon': lon, 'format': 'json', 'addressdetails': 1
            }, timeout=15)
            if r.ok:
                d = r.json()
                addr = d.get('address', {})
                print(f"  [{chid}] '{name[:50] if name else 'N/A'}' [{country}]")
                print(f"       city='{extract_city(addr)}' state='{extract_state(addr)}' zip='{addr.get('postcode','')}'")
                print(f"       street='{build_street(addr)}'")
            else:
                print(f"  [{chid}] HTTP {r.status_code}")
        except Exception as e:
            print(f"  [{chid}] Error: {e}")
        time.sleep(0.05)
    print(f"\n  ... and {total - 5:,} more")
    db.close()
    sys.exit(0)

# ── Process with thread pool ──
CHUNK = 10  # commit frequently so progress survives restarts, visible for review
batch = []
updated = 0
filled_addr = 0
snapped_count = 0
failed = 0
no_result = 0
no_result_count = 0  # for periodic logging
country_filled = 0
ok_count = 0  # for spot-check sampling
start = time.time()

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = {executor.submit(reverse_one, row): row for row in rows}
    pbar = tqdm(total=total, desc="Reverse geocoding", unit='rec')
    
    for future in as_completed(futures):
        pbar.update(1)
        try:
            result = future.result()
        except Exception as e:
            failed += 1
            tqdm.write(f"  CRASH: {e}")
            continue
        code = result[0]
        
        if code == 'ok':
            _, chid, street, city, state, postcode, new_lat, new_lon, nom_country, dist, lat, lon, name, country = result
            ok_count += 1
            # Live stream: show every match
            tqdm.write(f"  [#{chid}] ({lat:.4f},{lon:.4f}) '{name[:50] if name else 'N/A'}' [{country}]")
            tqdm.write(f"           -> {city}, {state} | {street[:60] if street else 'no street'} | snap={dist*1000:.0f}m")
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
                for b in batch:
                    updated += 1
                    if b[0]: filled_addr += 1
                    if b[6]: country_filled += 1
                if not NO_SNAP:
                    snapped_count += len(batch)
                batch = []
        elif code == 'http_error':
            _, chid, status, *_ = result
            failed += 1
            if failed <= 5:
                tqdm.write(f"  HTTP {status} for id={chid}")
        elif code == 'error':
            _, chid, err, *_ = result
            failed += 1
            if failed <= 5:
                tqdm.write(f"  Error id={chid}: {err[:80]}")
        elif code in ('no_result', 'no_city'):
            _, chid, lat, lon, name, country = result
            no_result += 1
            no_result_count += 1
            tqdm.write(f"  [{code}] id={chid} ({lat:.5f},{lon:.5f}) '{name[:40] if name else 'N/A'}' [{country}]")
    
    pbar.close()

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
    for b in batch:
        updated += 1
        if b[0]: filled_addr += 1
        if b[6]: country_filled += 1
    if not NO_SNAP:
        snapped_count += len(batch)

elapsed = time.time() - start
print(f"\n{'='*60}")
print(f"COMPLETE: {total:,} processed in {elapsed:.0f}s ({total/elapsed:.1f} rec/s)")
print(f"  Updated: {updated:,} | Filled city: {updated:,} | Filled address: {filled_addr:,}")
print(f"  Filled country: {country_filled:,} | Snapped coords: {snapped_count:,}")
print(f"  Failed: {failed:,} | No result: {no_result:,}")
print(f"  DB: {DB}")
db.close()

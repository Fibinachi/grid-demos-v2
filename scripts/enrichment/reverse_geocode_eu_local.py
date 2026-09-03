"""
Reverse-geocode EU/AU churches using LOCAL Nominatim (WSL, port 8088).
High-throughput: 8 threads, no rate limit. Adapted from reverse_geocode_nominatim_local.py.
Fills: address, city, state, zip, country for churches with coordinates.

Usage:
  python scripts/enrichment/reverse_geocode_eu_local.py --country FR
  python scripts/enrichment/reverse_geocode_eu_local.py --country DE,IT,ES
  python scripts/enrichment/reverse_geocode_eu_local.py --all-eu
  python scripts/enrichment/reverse_geocode_eu_local.py --country AU
"""
import sqlite3, requests, time, sys, os, math, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'http://127.0.0.1:8088/reverse'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
THREADS = 8

# Parse args
COUNTRIES = []
for a in sys.argv:
    if a.startswith('--country='):
        COUNTRIES = [c.strip() for c in a.split('=',1)[1].split(',')]
    elif a == '--all-eu':
        COUNTRIES = ['FR','DE','IT','ES','GB','PL','AT','NL','BE','CH','PT','SE','DK','NO','FI','IE','CZ','GR','HU','RO']
    elif a == '--dry-run':
        DRY_RUN = True

DRY_RUN = '--dry-run' in sys.argv
NO_SNAP = '--no-snap' in sys.argv

if not COUNTRIES:
    print("Usage: --country=FR,DE,IT or --all-eu")
    sys.exit(1)

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1); dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def build_street(addr):
    parts = []
    hn = addr.get('house_number', '')
    road = addr.get('road', '') or addr.get('pedestrian', '') or addr.get('footway', '') or addr.get('path', '')
    if hn and road: parts.append(f'{hn} {road}')
    elif road: parts.append(road)
    return ', '.join(parts) if parts else ''

def extract_city(addr):
    """Extract and validate city name from Nominatim address dict.
    Returns '' if the value looks scrambled (coordinates, HTML, too long, etc.)."""
    import html, re
    raw = (addr.get('city') or addr.get('town') or addr.get('village') or
           addr.get('hamlet') or addr.get('municipality') or addr.get('suburb') or '')
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
    return (addr.get('state') or addr.get('province') or addr.get('region') or addr.get('state_district'))

_coord_cache = {}
_cache_lock = threading.Lock()

def reverse_one(row):
    chid, lat, lon, country, name = row
    cache_key = (round(lat, 4), round(lon, 4))
    with _cache_lock:
        if cache_key in _coord_cache:
            return _coord_cache[cache_key]
    try:
        r = requests.get(NOMINATIM_URL, params={'lat':lat,'lon':lon,'format':'json','addressdetails':1,'accept-language':'en'}, timeout=15)
        if r.status_code != 200:
            result = ('http_error', chid, lat, lon, name, country)
            _coord_cache[cache_key] = result; return result
        data = r.json()
        if not data or 'address' not in data:
            result = ('no_result', chid, lat, lon, name, country)
            _coord_cache[cache_key] = result; return result
        addr = data['address']
        city = extract_city(addr)
        if not city:
            county = addr.get('county', '')
            if county and len(county) <= 50 and county.count(',') < 2:
                city = county
            else:
                result = ('no_city', chid, lat, lon, name, country)
                _coord_cache[cache_key] = result; return result
        state = extract_state(addr)
        postcode = addr.get('postcode', '')
        street = build_street(addr)
        nom_country = addr.get('country', '')
        new_lat, new_lon = float(data.get('lat', lat)), float(data.get('lon', lon))
        dist = haversine_km(lat, lon, new_lat, new_lon) if not NO_SNAP else 0
        if NO_SNAP: new_lat, new_lon = lat, lon
        result = ('ok', chid, street, city, state, postcode, new_lat, new_lon, nom_country, dist, lat, lon, name, country)
        _coord_cache[cache_key] = result; return result
    except Exception as e:
        result = ('error', chid, str(e), lat, lon, name, country)
        _coord_cache[cache_key] = result; return result

# ── Main ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

placeholders = ','.join(['?' for _ in COUNTRIES])
c.execute(f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name FROM churches c 
    WHERE c.country IN ({placeholders}) AND (c.address IS NULL OR c.address='') 
    AND c.latitude IS NOT NULL ORDER BY c.id""", COUNTRIES)
rows = c.fetchall()
total = len(rows)
c_label = ','.join(COUNTRIES)
print(f"{c_label} missing address: {total:,}")
print(f"Server: local | Snap: {'OFF' if NO_SNAP else 'ON'} | Threads: {THREADS}")

if DRY_RUN:
    print("DRY RUN - sample:")
    for chid, lat, lon, country, name in rows[:5]:
        r = requests.get(NOMINATIM_URL, params={'lat':lat,'lon':lon,'format':'json','addressdetails':1}, timeout=15)
        d = r.json().get('address',{})
        print(f"  [#{chid}] '{name[:50]}' [{country}] -> {extract_city(d)}, {extract_state(d)} | {build_street(d)[:50]}")
    db.close(); sys.exit(0)

if total == 0:
    print("Nothing to do!"); db.close(); sys.exit(0)

CHUNK = 50
batch = []; updated = 0; filled_addr = 0; ok_count = 0
start = time.time()

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    futures = {executor.submit(reverse_one, row): row for row in rows}
    processed = 0
    for future in as_completed(futures):
        processed += 1
        result = future.result()
        code = result[0]
        if code == 'ok':
            _, chid, street, city, state, postcode, new_lat, new_lon, nom_country, dist, lat, lon, name, country = result
            ok_count += 1
            print(f"  [#{chid}] ({lat:.4f},{lon:.4f}) '{name[:45] if name else 'N/A'}' [{country}] -> {city}, {state} | {street[:45]}")
            batch.append((street, city, state, postcode, new_lat, new_lon, nom_country, chid))
            if len(batch) >= CHUNK:
                c.executemany("""UPDATE churches SET address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                    city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
                    state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                    zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
                    latitude=?, longitude=?,
                    country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END WHERE id=?""", batch)
                db.commit()
                for b in batch:
                    updated += 1
                    if b[0]: filled_addr += 1
                batch = []
        elif code == 'no_city':
            _, chid, lat, lon, name, country = result
            print(f"  [no_city] id={chid} ({lat:.5f},{lon:.5f}) '{name[:45] if name else 'N/A'}' [{country}]")
        
        # Progress line every 200 records
        if processed % 200 == 0:
            elapsed = time.time() - start
            rate = processed / elapsed
            eta = (total - processed) / rate / 60 if rate > 0 else 0
            print(f"  --- {processed:,}/{total:,} ({processed/total*100:.0f}%) | ok: {ok_count:,} | rate: {rate:.1f}/s | ETA: {eta:.0f}m ---", flush=True)

if batch:
    c.executemany("""UPDATE churches SET address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
        city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
        state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
        zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
        latitude=?, longitude=?,
        country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END WHERE id=?""", batch)
    db.commit()
    for b in batch:
        updated += 1
        if b[0]: filled_addr += 1

elapsed = time.time() - start
db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
    VALUES ('local_eu_geocode','reverse_geocode_eu_local.py',?,datetime('now'),'completed',
    ?||': '||?||' updated, '||?||' addresses in '||?||'s')""",
    (NOW, c_label, str(updated), str(filled_addr), f"{elapsed:.0f}"))
db.commit()
db.close()
print(f"\nDone in {elapsed/60:.0f}m — {updated:,} updated, {filled_addr:,} addresses filled")

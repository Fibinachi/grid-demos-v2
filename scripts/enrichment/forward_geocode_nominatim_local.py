"""
Forward-geocode churches using LOCAL Nominatim (WSL on port 8088).
Turns address+city+state into lat/lon + refined address.
High-throughput: 8 threads, no rate limit.

FILLS: latitude, longitude
REFINES: address (street), city, state, zip, country

Usage:
  python scripts/enrichment/forward_geocode_nominatim_local.py           # US null-GPS with full address
  python scripts/enrichment/forward_geocode_nominatim_local.py --all     # ALL null-GPS with full address
  python scripts/enrichment/forward_geocode_nominatim_local.py --city-only  # city+state only (centroid)
  python scripts/enrichment/forward_geocode_nominatim_local.py --dry-run  # test 5 samples
  python scripts/enrichment/forward_geocode_nominatim_local.py --limit 100
"""
import sqlite3, requests, time, sys, os, math, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'http://127.0.0.1:8088/search'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
THREADS = 8

DRY_RUN = '--dry-run' in sys.argv
ALL_MODE = '--all' in sys.argv
CITY_ONLY = '--city-only' in sys.argv
LIMIT = None
for a in sys.argv:
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])


def build_query(row):
    """Build search query from address components."""
    chid, name, address, city, state, zip_code, country = row
    # Build query from most specific to least
    parts = []
    if address and address.strip():
        parts.append(address.strip())
    if name and name.strip():
        parts.append(name.strip())
    if city and city.strip():
        parts.append(city.strip())
    if state and state.strip():
        parts.append(state.strip())
    return ', '.join(parts), chid, name, address, city, state, zip_code, country


def build_query_city_only(row):
    """Build search query from city+state only (for centroid geocoding)."""
    chid, name, city, state, country = row
    parts = []
    if name and name.strip():
        parts.append(name.strip())
    if city and city.strip():
        parts.append(city.strip())
    if state and state.strip():
        parts.append(state.strip())
    return ', '.join(parts), chid, name, city, state, country


def extract_street(addr_dict):
    """Extract street address from Nominatim address dict."""
    hn = addr_dict.get('house_number', '')
    road = addr_dict.get('road', '') or addr_dict.get('pedestrian', '') or addr_dict.get('footway', '') or addr_dict.get('path', '')
    if hn and road:
        return f'{hn} {road}'
    return road or ''


def extract_city(addr_dict):
    return (addr_dict.get('city') or addr_dict.get('town') or addr_dict.get('village') or
            addr_dict.get('hamlet') or addr_dict.get('municipality') or
            addr_dict.get('suburb') or addr_dict.get('county'))


def extract_state(addr_dict):
    return (addr_dict.get('state') or addr_dict.get('province') or
            addr_dict.get('region') or addr_dict.get('state_district'))


def forward_one(query, chid, name, address, city, state, zip_code, country):
    """Forward geocode one record. Returns tuple for batch UPDATE."""
    try:
        r = requests.get(NOMINATIM_URL, params={
            'q': query, 'format': 'json', 'limit': 1,
            'addressdetails': 1, 'accept-language': 'en'
        }, timeout=15)
        if r.status_code != 200:
            return ('http_error', chid, r.status_code, query, name, country)
        data = r.json()
        if not data:
            return ('no_result', chid, query, name, country)
        result = data[0]
        new_lat = float(result['lat'])
        new_lon = float(result['lon'])
        addr_dict = result.get('address', {})
        street = extract_street(addr_dict)
        nom_city = extract_city(addr_dict)
        nom_state = extract_state(addr_dict)
        nom_zip = addr_dict.get('postcode', '')
        nom_country = addr_dict.get('country', '')
        return ('ok', chid, new_lat, new_lon, street, nom_city, nom_state, nom_zip, nom_country,
                query, name, address, city, state, zip_code, country)
    except Exception as e:
        return ('error', chid, str(e), query, name, country)


def forward_one_city(row_tuple):
    """Forward geocode city-only row."""
    query, chid, name, city, state, country = row_tuple
    return forward_one(query, chid, name, '', city, state, '', country)


# ── Connect ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# ── Build query ──
if CITY_ONLY:
    conditions = [
        "c.latitude IS NULL",
        "c.city IS NOT NULL AND c.city != ''",
        "c.state IS NOT NULL AND c.state != ''",
    ]
    if not ALL_MODE:
        conditions.append("c.country = 'US'")
    mode_label = 'city+state centroid'
    sql = f"""SELECT c.id, c.name, c.city, c.state, c.country
              FROM churches c WHERE {' AND '.join(conditions)} ORDER BY c.id"""
else:
    conditions = [
        "c.latitude IS NULL",
        "c.address IS NOT NULL AND c.address != '' AND c.address != 'None'",
        "c.city IS NOT NULL AND c.city != ''",
        "c.state IS NOT NULL AND c.state != ''",
    ]
    if not ALL_MODE:
        conditions.append("c.country = 'US'")
    mode_label = 'full address'
    sql = f"""SELECT c.id, c.name, c.address, c.city, c.state, c.zip, c.country
              FROM churches c WHERE {' AND '.join(conditions)} ORDER BY c.id"""

if LIMIT:
    sql += f' LIMIT {LIMIT}'

c.execute(sql)
rows = c.fetchall()
total = len(rows)
print(f"Forward geocode — {mode_label}: {total:,}")
print(f"Threads: {THREADS} | Dry run: {'YES' if DRY_RUN else 'NO'}")
print()

if total == 0:
    print("Nothing to do!")
    db.close()
    sys.exit(0)

if DRY_RUN:
    print("DRY RUN — will not write to DB. Sample:")
    session = requests.Session()
    sample_rows = rows[:5]
    for row in sample_rows:
        if CITY_ONLY:
            query, chid, name, city, state, country = build_query_city_only(row)
        else:
            query, chid, name, address, city, state, zip_code, country = build_query(row)
        try:
            r = session.get(NOMINATIM_URL, params={
                'q': query, 'format': 'json', 'limit': 1, 'addressdetails': 1
            }, timeout=15)
            if r.ok:
                data = r.json()
                if data:
                    d = data[0]
                    addr = d.get('address', {})
                    print(f"  [{chid}] '{name[:50] if name else 'N/A'}' [{country}]")
                    print(f"       query='{query[:80]}'")
                    print(f"       -> lat={d.get('lat')} lon={d.get('lon')}")
                    print(f"       -> city='{extract_city(addr)}' state='{extract_state(addr)}'")
                    print(f"       -> street='{extract_street(addr)}'")
                else:
                    print(f"  [{chid}] No results for '{query[:80]}'")
            else:
                print(f"  [{chid}] HTTP {r.status_code}")
        except Exception as e:
            print(f"  [{chid}] Error: {e}")
        time.sleep(0.05)
    print(f"\n  ... and {total - 5:,} more")
    db.close()
    sys.exit(0)

# ── Process with thread pool ──
CHUNK = 500
batch = []
updated = 0
filled_addr = 0
filled_city = 0
failed = 0
no_result = 0
start = time.time()

# Build query strings up front
print("Building query strings...")
if CITY_ONLY:
    queries = [build_query_city_only(row) for row in rows]
else:
    queries = [build_query(row) for row in rows]

with ThreadPoolExecutor(max_workers=THREADS) as executor:
    if CITY_ONLY:
        futures = {executor.submit(forward_one_city, q): q for q in queries}
    else:
        futures = {executor.submit(forward_one, *q): q for q in queries}
    
    pbar = tqdm(total=total, desc="Forward geocoding", unit='rec')
    
    for future in as_completed(futures):
        pbar.update(1)
        result = future.result()
        code = result[0]
        
        if code == 'ok':
            _, chid, new_lat, new_lon, street, nom_city, nom_state, nom_zip, nom_country, *_ = result
            batch.append((new_lat, new_lon, street, nom_city, nom_state, nom_zip, nom_country, chid))
            if len(batch) >= CHUNK:
                c.executemany(
                    """UPDATE churches SET 
                       latitude=?, longitude=?,
                       address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                       city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
                       state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                       zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
                       country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END
                       WHERE id=?""",
                    batch
                )
                db.commit()
                for b in batch:
                    updated += 1
                    if b[2]: filled_addr += 1
                    if b[3]: filled_city += 1
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
        elif code == 'no_result':
            _, chid, query, name, country = result
            no_result += 1
            if no_result <= 5:
                tqdm.write(f"  [no_result] id={chid} '{name[:40] if name else 'N/A'}' [{country}] q='{query[:60]}'")
    
    pbar.close()

# Flush remaining
if batch:
    c.executemany(
        """UPDATE churches SET 
           latitude=?, longitude=?,
           address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
           city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END,
           state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
           zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
           country=CASE WHEN country IS NULL OR country='' THEN ? ELSE country END
           WHERE id=?""",
        batch
    )
    db.commit()
    for b in batch:
        updated += 1
        if b[2]: filled_addr += 1
        if b[3]: filled_city += 1

elapsed = time.time() - start
print(f"\n{'='*60}")
print(f"COMPLETE: {total:,} processed in {elapsed:.0f}s ({total/elapsed:.1f} rec/s)")
print(f"  Updated: {updated:,} | Filled address: {filled_addr:,} | Filled city: {filled_city:,}")
print(f"  Failed: {failed:,} | No result: {no_result:,}")
print(f"  DB: {DB}")
db.close()

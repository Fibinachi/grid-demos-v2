"""
Reverse-geocode churches using Nominatim (public API or local WSL instance).
FILLS: address (street), city, state, zip, country (if blank)
CORRECTS: latitude/longitude -> snapped to Nominatim centroid

Rate limit: 1 req/s (public API). No limit for local.

Usage:
  python scripts/enrichment/reverse_geocode_nominatim.py                  # non-US missing city (public API)
  python scripts/enrichment/reverse_geocode_nominatim.py --local          # use WSL Nominatim (port 8088)
  python scripts/enrichment/reverse_geocode_nominatim.py --us             # US missing address
  python scripts/enrichment/reverse_geocode_nominatim.py --dry-run         # test 5 samples
  python scripts/enrichment/reverse_geocode_nominatim.py --limit 100
  python scripts/enrichment/reverse_geocode_nominatim.py --no-snap         # don't correct coords
  python scripts/enrichment/reverse_geocode_nominatim.py --skip-months=12  # skip entries processed in last 12mo (default 6)
  python scripts/enrichment/reverse_geocode_nominatim.py --force           # re-process even if done recently
"""
import sqlite3, requests, time, sys, os, math, subprocess, random
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/reverse'
LOCAL_NOMINATIM_URL = 'http://127.0.0.1:8088/reverse'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
# Randomized UA suffix to help Nominatim distinguish restarts
UA = f'GRID/1.0 (https://github.com/GRID-project; academic research) run-{random.randint(1000,9999)}'

def db_retry(func, *args, max_retries=10, wait=10, **kwargs):
    """Call func with retry on database lock."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                print(f"  DB locked, retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise

DRY_RUN = '--dry-run' in sys.argv
NO_SNAP = '--no-snap' in sys.argv
US_MODE = '--us' in sys.argv
AFRICA_MODE = '--africa' in sys.argv
ME_MODE = '--middle-east' in sys.argv
ALL_MODE = '--all' in sys.argv
LOCAL_MODE = '--local' in sys.argv
FORCE = '--force' in sys.argv
NO_FALLBACK = '--no-fallback' in sys.argv
WORKERS = 8  # default thread count
SKIP_MONTHS = 6  # default: skip entries geocoded in last 6 months
LIMIT = None
COUNTRY = None  # single country mode
for i, a in enumerate(sys.argv):
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a == '--limit' and i + 1 < len(sys.argv):
        try:
            LIMIT = int(sys.argv[i + 1])
        except ValueError:
            pass
    if a.startswith('--skip-months='):
        SKIP_MONTHS = int(a.split('=')[1])
    if a.startswith('--workers='):
        WORKERS = int(a.split('=')[1])
    elif a == '--workers' and i + 1 < len(sys.argv):
        WORKERS = int(sys.argv[i + 1])
    if a.startswith('--country='):
        COUNTRY = a.split('=')[1].upper()
    elif a == '--country' and i + 1 < len(sys.argv):
        COUNTRY = sys.argv[i + 1].upper()

# Use local URL if --local
if LOCAL_MODE:
    NOMINATIM_URL = LOCAL_NOMINATIM_URL
    RATE_DELAY = 0  # local: no rate limit needed
else:
    RATE_DELAY = 1.1   # public: polite 1 req/s


# ── Init HTTP sessions ──
if LOCAL_MODE:
    local_session = requests.Session()
else:
    session = requests.Session()
    session.headers.update({'User-Agent': UA})


def nominatim_reverse(lat, lon):
    """Query Nominatim reverse geocode. Uses direct HTTP to local instance when --local, public API otherwise."""
    if LOCAL_MODE:
        # WSL2 forwards localhost ports to the VM — direct requests work
        try:
            r = local_session.get(LOCAL_NOMINATIM_URL, params={
                'lat': lat, 'lon': lon, 'format': 'json',
                'addressdetails': 1, 'accept-language': 'en'
            }, timeout=15)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None
    else:
        try:
            r = session.get(NOMINATIM_URL, params={
                'lat': lat, 'lon': lon, 'format': 'json',
                'addressdetails': 1, 'accept-language': 'en'
            }, timeout=15)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None


def geonames_nearest(lat, lon, country=None):
    """Fallback: find nearest GeoNames place within ~50km. Returns (city, state, country)."""
    # Search expanding bounding box: 0.1° → 0.3° → 0.5° (~11 → 33 → 55 km)
    for delta in [0.1, 0.3, 0.5]:
        sql = """SELECT name, admin1, country_code, latitude, longitude, population
                 FROM geonames_places
                 WHERE latitude BETWEEN ? AND ?
                   AND longitude BETWEEN ? AND ?
                   AND feature_class = 'P'"""
        params = [lat - delta, lat + delta, lon - delta, lon + delta]
        if country:
            sql += " AND country_code = ?"
            params.append(country)
        sql += " ORDER BY population DESC LIMIT 3"
        try:
            rows = c.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return ('', '', '')  # table doesn't exist yet
        if rows:
            best = min(rows, key=lambda r: haversine_km(lat, lon, r[3], r[4]))
            dist = haversine_km(lat, lon, best[3], best[4])
            if dist < delta * 111:  # within the search box
                return (best[0], best[1] or '', best[2])
    return ('', '', '')


def haversine_km(lat1, lon1, lat2, lon2):
    """Distance in km between two points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_street(addr):
    """Build street address from Nominatim address dict."""
    parts = []
    hn = addr.get('house_number', '')
    road = addr.get('road', '') or addr.get('pedestrian', '') or addr.get('footway', '') or addr.get('path', '')
    if hn and road:
        parts.append(f'{hn} {road}')
    elif road:
        parts.append(road)
    # Add neighbourhood/suburb for context
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
    if re.search(r'\d+\.\d+[°]', raw):
        return ''
    if len(raw) > 80:
        return ''
    if raw.count(',') >= 3:
        return ''
    if re.search(r'\b(is one|is a|located in|directly subject|under the)\b', raw, re.IGNORECASE):
        return ''
    return raw


def extract_state(addr):
    """Extract state/province/region from Nominatim address."""
    return (addr.get('state') or addr.get('province') or
            addr.get('region') or addr.get('state_district') or '')


# ── Connect ──
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# ── Tracking table: skip entries geocoded within SKIP_MONTHS ──
c.execute("""CREATE TABLE IF NOT EXISTS nominatim_geocode_log (
    church_id INTEGER PRIMARY KEY,
    processed_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success','no_city','no_result','http_error','exception')),
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    new_lat REAL,
    new_lon REAL,
    snap_m REAL,
    country TEXT
)""")
db.commit()

skip_cutoff = (datetime.now(timezone.utc).replace(day=1) if SKIP_MONTHS > 1 
               else datetime.now(timezone.utc)).strftime('%Y-%m-%d')
# Use month-level granularity: skip if processed in same calendar month
from datetime import datetime as dt
import calendar
now_utc = dt.now(timezone.utc)
# Calculate cutoff: first day of month SKIP_MONTHS months ago
cutoff_month = now_utc.month - SKIP_MONTHS
cutoff_year = now_utc.year
while cutoff_month < 1:
    cutoff_month += 12
    cutoff_year -= 1
skip_cutoff = f'{cutoff_year}-{cutoff_month:02d}-01'

print(f"Skip mode: entries geocoded since {skip_cutoff} ({SKIP_MONTHS} months){' (FORCED OFF)' if FORCE else ''}")
print(f"Mode: {'LOCAL (WSL :8088)' if LOCAL_MODE else 'PUBLIC API'} | Workers: {WORKERS} | Rate: {RATE_DELAY}s delay")

# ── Fetch records ──
skip_join = ""
if not FORCE:
    skip_join = f"""AND c.id NOT IN (
        SELECT church_id FROM nominatim_geocode_log 
        WHERE processed_at >= '{skip_cutoff}'
    )"""

if US_MODE:
    sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name
    FROM churches c
    WHERE c.country = 'US'
      AND c.latitude IS NOT NULL
      AND (c.address IS NULL OR c.address = '')
      {skip_join}
    ORDER BY c.id"""
    mode_label = 'US missing address'
elif AFRICA_MODE:
    africa = ['NG','ZA','EG','DZ','MA','SD','ET','KE','UG','GH','TZ','CM','CI','CD','SN',
              'ZW','BW','MW','LY','TN','ZM','BF','ML','NE','BJ','RW','SO','SL','LR','TG',
              'CG','GM','GW','LS','SZ','BI','NA','GA','TD','MR','CV','DJ','KM','ST','SC',
              'GQ','ER','MU','CF','AO','MG','MZ','SS']
    sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name
    FROM churches c
    WHERE c.latitude IS NOT NULL
      AND (c.address IS NULL OR c.address = '')
      AND c.country IN ({','.join(['?' for _ in africa])})
      {skip_join}
    ORDER BY c.id"""
    mode_label = 'Africa missing address'
elif ME_MODE:
    middle_east = ['YE','SA','IR','IQ','SY','JO','LB','KW','AE','OM','QA','BH','PS','IL','EG']
    sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name
    FROM churches c
    WHERE c.latitude IS NOT NULL
      AND (c.address IS NULL OR c.address = '')
      AND c.country IN ({','.join(['?' for _ in middle_east])})
      {skip_join}
    ORDER BY c.id"""
    mode_label = 'Middle East missing address'
elif ALL_MODE:
    sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name
    FROM churches c
    WHERE c.latitude IS NOT NULL AND c.latitude != 0
      AND (c.address IS NULL OR c.address = '')
      AND c.country != 'US'
      {skip_join}
    ORDER BY c.id"""
    mode_label = 'ALL non-US missing address'
else:
    sql = f"""SELECT c.id, c.latitude, c.longitude, c.country, c.name
    FROM churches c
    WHERE (c.city IS NULL OR c.city = '')
      AND c.latitude IS NOT NULL
      AND c.country != 'US'
      {skip_join}
    ORDER BY c.id"""
    mode_label = 'non-US missing city'
if LIMIT:
    sql += f' LIMIT {LIMIT}'

# Single-country override
if COUNTRY:
    # Replace the WHERE clause to filter for single country
    sql = sql.replace(
        "AND c.country != 'US'",
        f"AND c.country = '{COUNTRY}'"
    ).replace(
        "c.country = 'US'",
        f"c.country = '{COUNTRY}'"
    )
    # If neither was there, add it
    if f"c.country = '{COUNTRY}'" not in sql:
        sql = sql.replace("WHERE", f"WHERE c.country = '{COUNTRY}' AND")
    mode_label = f'{COUNTRY} missing address'

if AFRICA_MODE:
    c.execute(sql, africa)
elif ME_MODE:
    c.execute(sql, middle_east)
else:
    c.execute(sql)
rows = c.fetchall()
total = len(rows)
print(f"{mode_label}: {total:,}")
req_rate = 1/RATE_DELAY if RATE_DELAY > 0 else 20
print(f"Snap coords: {'OFF' if NO_SNAP else 'ON'} | Dry run: {'YES' if DRY_RUN else 'NO'} | ETA: {total/req_rate/3600:.1f}h at {req_rate:.0f} req/s")
print()

if total == 0:
    print("Nothing to do!")
    db.close()
    sys.exit(0)

if DRY_RUN:
    print("DRY RUN — will not write to DB. Sample:")
    for chid, lat, lon, country, name in rows[:5]:
        try:
            d = nominatim_reverse(lat, lon)
            if d and 'address' in d:
                addr = d.get('address', {})
                street = build_street(addr)
                city = extract_city(addr)
                state = extract_state(addr)
                zipcode = addr.get('postcode', '')
                new_lat = float(d.get('lat', lat))
                new_lon = float(d.get('lon', lon))
                dist = haversine_km(lat, lon, new_lat, new_lon)
                print(f"  [{chid}] '{name[:50] if name else 'N/A'}'")
                print(f"       old=({lat:.5f},{lon:.5f}) new=({new_lat:.5f},{new_lon:.5f}) snap={dist*1000:.0f}m")
                print(f"       street='{street}' city='{city}' state='{state}' zip='{zipcode}'")
            else:
                print(f"  [{chid}] No result from Nominatim")
        except Exception as e:
            print(f"  [{chid}] Error: {e}")
        time.sleep(RATE_DELAY)
    print(f"\n  ... and {total - 5:,} more")
    db.close()
    sys.exit(0)

# ── Process (threaded HTTP, serial DB) ──
CHUNK = 500      # DB commit batch size
FETCH_CHUNK = 2000  # how many rows to submit to thread pool at once
db_lock = Lock()
batch = []
updated = 0
filled_addr = 0
failed = 0
no_result = 0
country_filled = 0
start = time.time()

def process_one(row):
    """Make HTTP request + extract fields. Returns result tuple."""
    chid, lat, lon, country, name = row
    try:
        data = nominatim_reverse(lat, lon)
        if data is None:
            return ('http_error', chid, lat, lon, country, name, None)
        if not data or 'address' not in data:
            return ('no_result', chid, lat, lon, country, name, None)
        addr = data['address']
        city = extract_city(addr)
        if not city:
            county = addr.get('county', '')
            if county and len(county) <= 50 and county.count(',') < 2:
                city = county
        state = extract_state(addr)
        postcode = addr.get('postcode', '')
        street = build_street(addr)
        nom_country = addr.get('country', '')
        new_lat = float(data.get('lat', lat))
        new_lon = float(data.get('lon', lon))
        return ('ok', chid, lat, lon, country, name, (street, city, state, postcode, new_lat, new_lon, nom_country))
    except Exception as e:
        return ('exception', chid, lat, lon, country, name, str(e))

# Pre-fetch all rows
all_rows = list(rows)
total = len(all_rows)

# Process in chunks to limit future count
with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    pbar = tqdm(total=total, desc="Reverse geocoding", unit='rec')
    
    for chunk_start in range(0, total, FETCH_CHUNK):
        chunk = all_rows[chunk_start:chunk_start + FETCH_CHUNK]
        futures = {executor.submit(process_one, row): row for row in chunk}
        
        for future in as_completed(futures):
            result = future.result()
            status = result[0]
            chid, lat, lon, country, name = result[1:6]
            
            if status == 'http_error':
                failed += 1
                try:
                    with db_lock:
                        c.execute("INSERT OR REPLACE INTO nominatim_geocode_log(church_id,processed_at,status) VALUES(?,?,?)",
                                  (chid, NOW, 'http_error'))
                        db.commit()
                except Exception:
                    pass
            elif status == 'no_result':
                no_result += 1
                try:
                    with db_lock:
                        c.execute("INSERT OR REPLACE INTO nominatim_geocode_log(church_id,processed_at,status,country) VALUES(?,?,?,?)",
                                  (chid, NOW, 'no_result', country))
                        db.commit()
                except Exception:
                    pass
            elif status == 'exception':
                failed += 1
                try:
                    with db_lock:
                        c.execute("INSERT OR REPLACE INTO nominatim_geocode_log(church_id,processed_at,status,country) VALUES(?,?,?,?)",
                                  (chid, NOW, 'exception', country))
                        db.commit()
                except Exception:
                    pass
            elif status == 'ok':
                street, city, state, postcode, new_lat, new_lon, nom_country = result[6]
                
                if not city:
                    no_result += 1
                    try:
                        with db_lock:
                            c.execute("INSERT OR REPLACE INTO nominatim_geocode_log(church_id,processed_at,status,country) VALUES(?,?,?,?)",
                                      (chid, NOW, 'no_city', country))
                            db.commit()
                    except Exception:
                        pass
                else:
                    if NO_SNAP:
                        new_lat, new_lon = lat, lon
                    
                    batch.append((street, city, state, postcode, new_lat, new_lon, nom_country, nom_country, chid))
                    
                    if len(batch) >= CHUNK:
                        def commit_batch():
                            with db_lock:
                                c.executemany(
                                    """UPDATE churches SET 
                                       address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                                       city=?, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                                       zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
                                       latitude=?, longitude=?,
                                       country=CASE WHEN country IS NULL OR country='' OR country!=? THEN ? ELSE country END
                                       WHERE id=?""",
                                    batch
                                )
                                for (bstreet, bcity, bstate, bzip, blat, blon, bcountry, _, bchid) in batch:
                                    c.execute("""INSERT OR REPLACE INTO nominatim_geocode_log
                                        (church_id, processed_at, status, street, city, state, zip, new_lat, new_lon, country)
                                        VALUES (?,?,?,?,?,?,?,?,?,?)""",
                                        (bchid, NOW, 'success', bstreet, bcity, bstate, bzip, blat, blon, bcountry))
                                db.commit()
                        db_retry(commit_batch)
                        for b in batch:
                            updated += 1
                            if b[0]: filled_addr += 1
                            if b[6]: country_filled += 1
                        batch = []
            
            pbar.update(1)
        
        # Rate limit for non-local mode (per chunk)
        if not LOCAL_MODE and RATE_DELAY > 0:
            time.sleep(RATE_DELAY * len(chunk) / WORKERS)
    
    pbar.close()

# ── Final flush ──
if batch:
    def flush_batch():
        with db_lock:
            c.executemany(
                """UPDATE churches SET 
                   address=CASE WHEN address IS NULL OR address='' THEN ? ELSE address END,
                   city=?, state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END,
                   zip=CASE WHEN zip IS NULL OR zip='' THEN ? ELSE zip END,
                   latitude=?, longitude=?,
                   country=CASE WHEN country IS NULL OR country='' OR country!=? THEN ? ELSE country END
                   WHERE id=?""",
                batch
            )
            for (bstreet, bcity, bstate, bzip, blat, blon, bcountry, _, bchid) in batch:
                c.execute("""INSERT OR REPLACE INTO nominatim_geocode_log
                    (church_id, processed_at, status, street, city, state, zip, new_lat, new_lon, country)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (bchid, NOW, 'success', bstreet, bcity, bstate, bzip, blat, blon, bcountry))
            db.commit()
    db_retry(flush_batch)
    for b in batch:
        updated += 1
        if b[0]: filled_addr += 1
        if b[6]: country_filled += 1

elapsed = time.time() - start
print(f"\nDone in {elapsed:.0f}s ({elapsed/60:.1f}m)")
print(f"  Updated:        {updated:,}")
print(f"  Address filled: {filled_addr:,}")
print(f"  Country filled: {country_filled:,}")
print(f"  No city found:  {no_result:,}")
print(f"  Failed:         {failed:,}")
print(f"  Rate:           {total/elapsed:.1f} rec/s ({total/elapsed/WORKERS:.1f} req/s per worker)")

# ── Tracking table summary ──
c.execute("SELECT COUNT(*) FROM nominatim_geocode_log")
log_total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM nominatim_geocode_log WHERE processed_at >= ?", (NOW[:10],))
log_today = c.fetchone()[0]
print(f"  Tracking log:   {log_total:,} total entries ({log_today:,} today)")

# ── Provenance ──
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provenance_log'")
if c.fetchone():
    notes = f"{'Local WSL' if LOCAL_MODE else 'Public'} Nominatim reverse geocode. Filled address/city/state/zip. Coords snapped={'N' if NO_SNAP else 'Y'}. No city: {no_result}, Failed: {failed}"
    def write_provenance():
        c.execute("""INSERT INTO provenance_log (source, script_name, records_attempted, records_matched, notes)
                     VALUES (?,?,?,?,?)""", (
            'nominatim_docker', 'reverse_geocode_nominatim.py',
            total, updated, notes
        ))
        db.commit()
    try:
        db_retry(write_provenance)
    except sqlite3.OperationalError:
        print("  Warning: Could not write provenance (DB locked)")

# ── Summary ──
if US_MODE:
    c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND latitude IS NOT NULL AND (address IS NULL OR address='')")
    remaining = c.fetchone()[0]
    print(f"  Remaining US w/o address: {remaining:,}")
else:
    c.execute("SELECT COUNT(*) FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL AND country!='US'")
    remaining = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE (city IS NULL OR city='') AND latitude IS NOT NULL")
    total_remaining = c.fetchone()[0]
    print(f"  Remaining non-US w/o city: {remaining:,}")
    print(f"  Remaining total w/o city:  {total_remaining:,}")

db.close()

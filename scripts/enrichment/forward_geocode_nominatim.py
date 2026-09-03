"""
Forward-geocode ungeocoded churches using Nominatim public API.
Processes countries from least to most ungeocoded entries.

FILLS: latitude, longitude
REFINES: address (street), city, state, zip, country
SOURCE: https://nominatim.openstreetmap.org (1 req/s rate limit)

Usage:
  python scripts/enrichment/forward_geocode_nominatim.py              # all ungeocoded, least->most
  python scripts/enrichment/forward_geocode_nominatim.py --dry-run    # show sample queries, no DB writes
  python scripts/enrichment/forward_geocode_nominatim.py --limit 100  # cap total records
  python scripts/enrichment/forward_geocode_nominatim.py --country US # single country only
"""
import sqlite3
import requests
import time
import sys
import os
from datetime import datetime, timezone
from tqdm import tqdm

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'GRID/1.0 (global religious infrastructure; charlesaprescott@outlook.com)'
DELAY = 1.05          # seconds between requests (Nominatim limit: 1/s)
COMMIT_EVERY = 200    # batch commit size
TIMEOUT = 15          # HTTP timeout
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

DRY_RUN = '--dry-run' in sys.argv
SINGLE_COUNTRY = None
LIMIT = None
for i, a in enumerate(sys.argv):
    if a.startswith('--country='):
        SINGLE_COUNTRY = a.split('=', 1)[1]
    elif a == '--country' and i + 1 < len(sys.argv):
        SINGLE_COUNTRY = sys.argv[i + 1]
    if a.startswith('--limit='):
        LIMIT = int(a.split('=', 1)[1])
    elif a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])


# ── Query building ──

def build_query(row):
    """Build search query from available address components. Returns (query, chid, ...)."""
    chid, name, address, city, state, zip_code, country = row
    parts = []
    if address and address.strip():
        addr = address.strip().rstrip(',').strip()
        if addr and addr.lower() not in ('school', 'tbd', 'n/a', 'church', 'none'):
            parts.append(addr)
    if name and name.strip():
        parts.append(name.strip())
    if city and city.strip():
        parts.append(city.strip())
    if state and state.strip():
        parts.append(state.strip())
    if zip_code and zip_code.strip():
        parts.append(zip_code.strip())
    if not parts:
        return None
    return ', '.join(parts)


# ── Address extraction ──

def extract_street(addr_dict):
    hn = addr_dict.get('house_number', '')
    road = addr_dict.get('road', '') or addr_dict.get('pedestrian', '') or \
           addr_dict.get('footway', '') or addr_dict.get('path', '')
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


# ── Geocode one record ──

def geocode_one(query, chid, name, address, city, state, zip_code, country):
    """Call Nominatim for one record. Returns result tuple."""
    try:
        r = requests.get(
            NOMINATIM_URL,
            params={
                'q': query,
                'format': 'json',
                'limit': 1,
                'addressdetails': 1,
                'accept-language': 'en',
            },
            headers={'User-Agent': USER_AGENT},
            timeout=TIMEOUT,
        )

        if r.status_code == 429:
            time.sleep(5)  # back off on rate limit
            r = requests.get(NOMINATIM_URL, params={
                'q': query, 'format': 'json', 'limit': 1,
                'addressdetails': 1, 'accept-language': 'en',
            }, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)

        if r.status_code != 200:
            return ('http_error', chid, r.status_code, query, name, country)

        data = r.json()
        if not data:
            return ('no_result', chid, query, name, country)

        result = data[0]
        new_lat = float(result['lat'])
        new_lon = float(result['lon'])

        if not (-90 <= new_lat <= 90 and -180 <= new_lon <= 180):
            return ('bad_coords', chid, new_lat, new_lon, query, name, country)

        addr_dict = result.get('address', {})
        street = extract_street(addr_dict)
        nom_city = extract_city(addr_dict) or ''
        nom_state = extract_state(addr_dict) or ''
        nom_zip = addr_dict.get('postcode', '')
        nom_country = addr_dict.get('country', '')

        return ('ok', chid, new_lat, new_lon, street, nom_city, nom_state, nom_zip, nom_country,
                query, name, address, city, state, zip_code, country)

    except requests.Timeout:
        return ('timeout', chid, query, name, country)
    except Exception as e:
        return ('error', chid, str(e)[:200], query, name, country)


# ── Log provenance ──

PROVENANCE_SOURCE = 'nominatim_forward'
PROVENANCE_VERSION = 1

# Map batch tuple positions to field names (batch has 13 values)
# (lat, lon, street_chk, street, city_chk, city, state_chk, state, zip_chk, zip, country_chk, country, chid)
BATCH_FIELDS = [
    (0, 'latitude'),
    (1, 'longitude'),
    (3, 'address'),    # index 3 = street value (index 2 is condition)
    (5, 'city'),
    (7, 'state'),
    (9, 'zip'),
    (11, 'country'),
]


def log_batch_provenance(c, batch, old_values_map):
    """Log enrichment_change_log entries for a batch of updates."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    inserts = []
    for item in batch:
        chid = item[12]  # last element is church_id
        old = old_values_map.get(chid, {})
        for idx, field_name in BATCH_FIELDS:
            new_val = item[idx]
            old_val = old.get(field_name)
            # Convert to string for comparison
            new_str = str(new_val) if new_val is not None else ''
            old_str = str(old_val) if old_val is not None else ''
            # Only log if value actually changed
            if new_str and new_str != old_str:
                inserts.append((chid, field_name, old_str, new_str,
                               PROVENANCE_SOURCE, PROVENANCE_VERSION, now))
    if inserts:
        c.executemany("""
            INSERT INTO enrichment_change_log
                (church_id, field_name, old_value, new_value, change_source, enrichment_version, changed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, inserts)


def fetch_old_values(c, church_ids):
    """Fetch current values for a list of church IDs. Returns dict of id -> {field: value}."""
    placeholders = ','.join('?' * len(church_ids))
    c.execute(f"""
        SELECT id, latitude, longitude, address, city, state, zip, country
        FROM churches WHERE id IN ({placeholders})
    """, church_ids)
    result = {}
    for row in c.fetchall():
        chid, lat, lon, addr, city, state, zip_code, country = row
        result[chid] = {
            'latitude': lat,
            'longitude': lon,
            'address': addr,
            'city': city,
            'state': state,
            'zip': zip_code,
            'country': country,
        }
    return result


# ── Main ──

def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    c = db.cursor()

    # Get ungeocoded counts by country (least -> most)
    c.execute("""
        SELECT country, COUNT(*)
        FROM churches
        WHERE (latitude IS NULL OR latitude = 0)
          AND name IS NOT NULL AND TRIM(name) != ''
        GROUP BY country
        ORDER BY COUNT(*) ASC
    """)
    country_counts = c.fetchall()

    if SINGLE_COUNTRY:
        country_counts = [(cntry, cnt) for cntry, cnt in country_counts
                          if cntry == SINGLE_COUNTRY]
        if not country_counts:
            print(f"Country '{SINGLE_COUNTRY}' not found or has no ungeocoded records.")
            db.close()
            return

    total_records = sum(cnt for _, cnt in country_counts)
    print(f"Forward geocode via Nominatim public API (1 req/s)")
    print(f"Countries to process: {len(country_counts)}")
    print(f"Total ungeocoded: {total_records:,}")
    eta_hours = total_records * DELAY / 3600
    print(f"ETA: {eta_hours:.1f} hours")
    if DRY_RUN:
        print("DRY RUN — no DB writes")
    print()

    grand_geocoded = 0
    grand_failed = 0
    grand_no_result = 0
    grand_start = time.time()

    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    for country_idx, (country, expected) in enumerate(country_counts):
        country_display = country or 'NULL'
        print(f"\n{'='*60}")
        print(f"[{country_idx+1}/{len(country_counts)}] {country_display}: {expected:,} ungeocoded")

        # Fetch records for this country
        where = "(latitude IS NULL OR latitude = 0) AND name IS NOT NULL AND TRIM(name) != ''"
        if country is None:
            c.execute(f"""
                SELECT id, name, address, city, state, zip, country
                FROM churches
                WHERE {where} AND country IS NULL
                ORDER BY id
            """)
        else:
            c.execute(f"""
                SELECT id, name, address, city, state, zip, country
                FROM churches
                WHERE {where} AND country = ?
                ORDER BY id
            """, (country,))

        rows = c.fetchall()

        if LIMIT and len(rows) > LIMIT:
            rows = rows[:LIMIT]

        country_total = len(rows)
        print(f"  Records to process: {country_total:,}")

        if country_total == 0:
            continue

        # Dry run — show samples only
        if DRY_RUN:
            print("  Sample queries:")
            session = requests.Session()
            for row in rows[:5]:
                query = build_query(row)
                if not query:
                    print(f"    [{row[0]}] SKIP — no query components")
                    continue
                try:
                    r = session.get(NOMINATIM_URL, params={
                        'q': query, 'format': 'json', 'limit': 1, 'addressdetails': 1
                    }, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT)
                    if r.ok and r.json():
                        d = r.json()[0]
                        addr = d.get('address', {})
                        print(f"    [{row[0]}] '{row[1][:50] if row[1] else 'N/A'}'")
                        print(f"         query='{query[:80]}'")
                        print(f"         -> lat={d['lat']} lon={d['lon']}")
                        print(f"         -> city='{extract_city(addr)}' state='{extract_state(addr)}'")
                    else:
                        print(f"    [{row[0]}] No result — '{query[:80]}'")
                except Exception as e:
                    print(f"    [{row[0]}] Error: {e}")
                time.sleep(0.3)
            print(f"  ... and {country_total - 5:,} more")
            continue

        # Process country
        batch = []
        country_geocoded = 0
        country_failed = 0
        country_no_result = 0
        country_start = time.time()

        pbar = tqdm(total=country_total, desc=f"  {country_display}", unit='rec')

        for row in rows:
            chid, name, address, city, state, zip_code, country_val = row
            query = build_query(row)

            if not query:
                pbar.update(1)
                country_no_result += 1
                continue

            # Safety: re-check that this record still needs geocoding
            c.execute("SELECT latitude, longitude FROM churches WHERE id=?", (chid,))
            existing = c.fetchone()
            if existing and existing[0] and existing[0] != 0:
                pbar.update(1)
                continue  # already geocoded somehow

            old_lat, old_lon = existing if existing else (None, None)

            result = geocode_one(query, chid, name, address, city, state, zip_code, country_val)
            code = result[0]

            if code == 'ok':
                _, chid2, new_lat, new_lon, street, nom_city, nom_state, nom_zip, nom_country, *_ = result
                # Each value twice: once for condition, once for assignment
                batch.append((new_lat, new_lon,
                             street, street,
                             nom_city, nom_city,
                             nom_state, nom_state,
                             nom_zip, nom_zip,
                             nom_country, nom_country,
                             chid2))

                if len(batch) >= COMMIT_EVERY:
                    # Fetch old values before update for provenance
                    batch_ids = [item[12] for item in batch]
                    old_vals = fetch_old_values(c, batch_ids)
                    c.executemany("""
                        UPDATE churches SET
                            latitude=?,
                            longitude=?,
                            address=CASE WHEN ? != '' THEN ? ELSE address END,
                            city=CASE WHEN ? != '' THEN ? ELSE city END,
                            state=CASE WHEN ? != '' THEN ? ELSE state END,
                            zip=CASE WHEN ? != '' THEN ? ELSE zip END,
                            country=CASE WHEN ? != '' THEN ? ELSE country END
                        WHERE id=?
                    """, batch)
                    log_batch_provenance(c, batch, old_vals)
                    db.commit()
                    country_geocoded += len(batch)
                    batch = []

            elif code == 'no_result':
                country_no_result += 1
            elif code == 'timeout':
                country_failed += 1
            elif code == 'http_error':
                country_failed += 1
                if country_failed <= 3:
                    tqdm.write(f"  HTTP {result[2]} for id={chid}")
            elif code in ('error', 'bad_coords'):
                country_failed += 1
                if country_failed <= 3:
                    tqdm.write(f"  {code}: id={chid} — {result[2][:80] if len(result)>2 else ''}")

            pbar.update(1)
            time.sleep(DELAY)

        # Flush remaining batch
        if batch:
            batch_ids = [item[12] for item in batch]
            old_vals = fetch_old_values(c, batch_ids)
            c.executemany("""
                UPDATE churches SET
                    latitude=?,
                    longitude=?,
                    address=CASE WHEN ? != '' THEN ? ELSE address END,
                    city=CASE WHEN ? != '' THEN ? ELSE city END,
                    state=CASE WHEN ? != '' THEN ? ELSE state END,
                    zip=CASE WHEN ? != '' THEN ? ELSE zip END,
                    country=CASE WHEN ? != '' THEN ? ELSE country END
                WHERE id=?
            """, batch)
            log_batch_provenance(c, batch, old_vals)
            db.commit()
            country_geocoded += len(batch)

        pbar.close()

        country_elapsed = time.time() - country_start
        print(f"  Done: {country_geocoded:,} geocoded | {country_no_result:,} no result | {country_failed:,} failed")
        print(f"  Time: {country_elapsed:.0f}s ({country_elapsed/country_total:.2f}s/rec)")

        grand_geocoded += country_geocoded
        grand_failed += country_failed
        grand_no_result += country_no_result

    grand_elapsed = time.time() - grand_start
    print(f"\n{'='*60}")
    print(f"COMPLETE: {grand_geocoded:,} geocoded | {grand_no_result:,} no result | {grand_failed:,} failed")
    print(f"Total time: {grand_elapsed:.0f}s ({grand_elapsed/3600:.1f}h)")
    print(f"DB: {DB}")
    db.close()


if __name__ == '__main__':
    main()

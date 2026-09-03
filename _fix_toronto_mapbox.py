"""Fix remaining Toronto CRA churches using Mapbox geocoding (Canadian addresses).

Falls back to Mapbox for churches that Nominatim/Address Points couldn't resolve.
Mapbox has better Canadian coverage and runs at ~10 req/sec (8 parallel workers).

Usage:
    python _fix_toronto_mapbox.py --write
"""
import csv, os, sqlite3, sys, time
from datetime import datetime, timezone
import urllib.request, urllib.parse, json

PROJECT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT, 'churches.db')
CRA_CSV = os.path.join(PROJECT, 'data', 'cra', 'cra_2024_identification.csv')

MAPBOX_KEY = os.environ.get("MAPBOX_API_KEY", "")
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
MAPBOX_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?access_token={key}&limit=1&country=CA"

WRITE = '--write' in sys.argv
CHUNK_SIZE = 50

def log(msg):
    print(f'  {msg}', flush=True)

def now_utc():
    return datetime.now(timezone.utc).isoformat()

def geocode_mapbox(address, city, province):
    """Geocode a Canadian address via Mapbox."""
    query = f"{address}, {city}, {province}, Canada"
    if not query.strip().strip(','):
        return None, None
    url = MAPBOX_URL.format(query=urllib.parse.quote(query), key=MAPBOX_KEY)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        features = data.get('features', [])
        if features:
            center = features[0].get('center', [])
            if len(center) == 2:
                return center[1], center[0]  # [lng, lat] -> (lat, lng)
    except:
        pass
    return None, None

def load_cra_toronto():
    cra = {}
    with open(CRA_CSV, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = (row.get('Legal Name') or '').strip().upper()
            if not name: continue
            city = (row.get('City') or '').strip()
            if city.upper() != 'TORONTO': continue
            addr1 = (row.get('Address Line 1') or '').strip()
            addr2 = (row.get('Address Line 2') or '').strip()
            cra[name] = {
                'address': f'{addr1} {addr2}'.strip(),
                'city': city,
                'province': (row.get('Province') or '').strip(),
            }
    log(f'{len(cra)} Toronto CRA addresses loaded')
    return cra

def main():
    cra_addrs = load_cra_toronto()

    db = sqlite3.connect(DB_PATH)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=30000')
    cur = db.cursor()

    # Get CRA Toronto churches still in clusters
    cur.execute('''
        SELECT c.id, c.name, c.latitude, c.longitude, c.source
        FROM churches c
        JOIN church_location l ON c.id = l.church_id
        INNER JOIN (SELECT latitude, longitude, COUNT(*) as cnt FROM churches
                    WHERE latitude IS NOT NULL AND source IN ('cra_2018','cra_2024')
                    GROUP BY latitude, longitude HAVING cnt > 1
        ) cl ON c.latitude = cl.latitude AND c.longitude = cl.longitude
        WHERE l.admin2_name = 'Toronto' AND c.source IN ('cra_2018','cra_2024')
    ''')
    churches = cur.fetchall()
    log(f'\n{len(churches)} Toronto CRA churches still in clusters')

    if not WRITE:
        log('\nDRY RUN - use --write to apply changes')
        db.close()
        return

    updated = 0
    failed = 0
    batch = []
    called = 0

    for i, (cid, name, old_lat, old_lon, source) in enumerate(churches):
        name_u = name.strip().upper() if name else ''
        cra = cra_addrs.get(name_u, {})
        cra_addr = cra.get('address', '')
        city = cra.get('city', '')
        prov = cra.get('province', '')

        if not cra_addr:
            failed += 1
            continue

        new_lat, new_lon = geocode_mapbox(cra_addr, city, prov)
        called += 1

        if new_lat is None:
            failed += 1
            print(f'[FAIL] {cid} | {name[:40]} | {cra_addr[:30]}, {city}', flush=True)
            continue

        old_str = f'{old_lat:.4f},{old_lon:.4f}' if old_lat else 'NULL'
        new_str = f'{new_lat:.4f},{new_lon:.4f}'
        print(f'[OK] {cid} | {name[:35]} | {old_str} -> {new_str} | {cra_addr[:28]}', flush=True)

        batch.append((cid, name, new_lat, new_lon, cra_addr, old_lat, old_lon))

        if len(batch) >= CHUNK_SIZE:
            _write_batch(db, cur, batch)
            updated += len(batch)
            batch = []
            time.sleep(0.5)

        # Rate limit: ~8 req/sec
        if called % 8 == 0:
            time.sleep(0.5)

    if batch:
        _write_batch(db, cur, batch)
        updated += len(batch)

    log(f'\n[DONE] Updated {updated}, {failed} failed ({called} API calls)')

    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    db.close()

def _write_batch(db, cur, batch):
    for cid, name, new_lat, new_lon, addr, old_lat, old_lon in batch:
        cur.execute(
            'UPDATE churches SET latitude = ?, longitude = ?, last_updated = ? WHERE id = ?',
            (new_lat, new_lon, now_utc(), cid)
        )
        cur.execute(
            'INSERT OR IGNORE INTO church_addresses (church_rowid, address_type, latitude, longitude, country, geocode_source, source, is_current, valid_from, church_id) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (cid, 'primary', new_lat, new_lon, 'Canada', 'mapbox_ca', 'toronto_mapbox', 1, now_utc(), cid)
        )
        cur.execute(
            'INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)',
            (cid, 'latitude', str(old_lat), str(new_lat), 'toronto_mapbox', now_utc())
        )
        cur.execute(
            'INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,?)',
            (cid, 'longitude', str(old_lon), str(new_lon), 'toronto_mapbox', now_utc())
        )
    db.commit()
    db.execute(
        'INSERT INTO provenance_log (source, script_name, started_at, completed_at, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?)',
        ('toronto_mapbox', '_fix_toronto_mapbox.py', now_utc(), now_utc(), len(batch), len(batch), 'completed', f'Mapbox-geocoded {len(batch)} Toronto CRA churches')
    )
    db.commit()

if __name__ == '__main__':
    main()

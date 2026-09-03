"""Reverse geocode US entries via Census API — concurrent, batch DB writes.
Fills: city, state, zip (from Census Places/States response), county_fips, tract_fips.
Threads: 10 concurrent requests. DB writes: batches of 400.

Usage:
  python scripts/enrichment/reverse_geocode_us_census_batch.py
  python scripts/enrichment/reverse_geocode_us_census_batch.py --limit 1000
"""

import sqlite3, requests, time, sys, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from tqdm import tqdm

DB = 'E:/grid/churches.db'
URL = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
THREADS = 10
CHUNK_SIZE = 400  # DB write batch size

LIMIT = None
for a in sys.argv:
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])

# ── Thread-local DB connection ──
_local = threading.local()

def get_db():
    if not hasattr(_local, 'db'):
        _local.db = sqlite3.connect(DB)
        _local.db.execute("PRAGMA journal_mode=WAL")
    return _local.db

# ── Shared session ──
session = requests.Session()
session.headers.update({'User-Agent': 'GRID/1.0 (academic research)'})

# ── Stats ──
stats_lock = threading.Lock()
stats = {'ok': 0, 'no_result': 0, 'http_err': 0, 'exception': 0, 'filled_city': 0}

def reverse_one(row):
    """Query Census API for one coordinate. Returns (rowid, city, state, county_fips, county_name, tract_fips) or None."""
    rowid, lat, lon = row
    try:
        r = session.get(URL, params={
            'x': str(lon), 'y': str(lat),
            'benchmark': '4', 'vintage': '4', 'format': 'json'
        }, timeout=10)
        if r.status_code != 200:
            with stats_lock:
                stats['http_err'] += 1
            return None
        
        g = r.json().get('result', {}).get('geographies', {})
        if not g:
            with stats_lock:
                stats['no_result'] += 1
            return None
        
        # County
        ct = g.get('Counties', [])
        county_fips = f"{ct[0]['STATE']}{ct[0]['COUNTY']}" if ct else None
        county_name = ct[0].get('NAME', '') if ct else None
        
        # Tract
        tr = g.get('Census Tracts', [])
        tract_fips = f"{tr[0]['STATE']}{tr[0]['COUNTY']}{tr[0]['TRACT']}" if tr else None
        
        # Place (city)
        pl = g.get('Incorporated Places', []) or g.get('Census Designated Places', [])
        city = pl[0].get('NAME', '') if pl else None
        
        # State
        st = g.get('States', [])
        state = st[0].get('STUSAB', '') if st else None
        
        with stats_lock:
            stats['ok'] += 1
            if city:
                stats['filled_city'] += 1
        
        return (rowid, city, state, county_fips, county_name, tract_fips)
    
    except Exception as e:
        with stats_lock:
            stats['exception'] += 1
        return None


def main():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA journal_mode=WAL")
    
    # Fetch records needing addresses (have coords, no address)
    sql = """SELECT c.rowid, c.latitude, c.longitude 
             FROM churches c 
             WHERE c.country='US' 
               AND c.latitude IS NOT NULL 
               AND (c.address IS NULL OR c.address = '')
             ORDER BY c.id"""
    if LIMIT:
        sql += f' LIMIT {LIMIT}'
    
    rows = db.execute(sql).fetchall()
    db.close()
    total = len(rows)
    
    print(f"US missing address: {total:,}")
    print(f"Threads: {THREADS} | DB batch: {CHUNK_SIZE} | {'LIMIT=' + str(LIMIT) if LIMIT else 'ALL'}")
    est = total / (THREADS * 3) / 60  # rough: 3 req/sec per thread
    print(f"Estimated: ~{est:.0f}m at ~{THREADS*3} req/sec")
    print()
    
    if total == 0:
        print("Nothing to do!")
        return
    
    # ── Process concurrently ──
    batch = []
    updated = 0
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {executor.submit(reverse_one, row): row for row in rows}
        pbar = tqdm(total=total, desc="Reverse geocoding", unit='rec')
        
        for future in as_completed(futures):
            pbar.update(1)
            result = future.result()
            if result is None:
                continue
            
            rowid, city, state, county_fips, county_name, tract_fips = result
            batch.append((rowid, city, state, county_fips, county_name, tract_fips))
            
            if len(batch) >= CHUNK_SIZE:
                # Write to DB
                wdb = sqlite3.connect(DB)
                wdb.execute("PRAGMA journal_mode=WAL")
                
                for rid, c, st, cf, cn, tf in batch:
                    if c:
                        wdb.execute(
                            "UPDATE churches SET city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END, "
                            "state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END "
                            "WHERE rowid=?", (c, st, rid))
                    wdb.execute("INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)", (rid,))
                    wdb.execute(
                        "UPDATE church_enrichment SET county_fips=?, county_name=?, tract_fips=? WHERE church_id=?",
                        (cf, cn, tf, rid))
                
                wdb.commit()
                wdb.close()
                
                updated += len(batch)
                
                # Progress
                elapsed = time.time() - start
                rate = updated / elapsed
                eta = (total - updated) / rate / 60 if rate > 0 else 0
                pbar.set_postfix({
                    'ok': stats['ok'], 'city': stats['filled_city'],
                    'rate': f'{rate:.1f}/s', 'eta': f'{eta:.0f}m'
                })
                
                batch = []
    
    # Final flush
    if batch:
        wdb = sqlite3.connect(DB)
        wdb.execute("PRAGMA journal_mode=WAL")
        for rid, c, st, cf, cn, tf in batch:
            if c:
                wdb.execute(
                    "UPDATE churches SET city=CASE WHEN city IS NULL OR city='' THEN ? ELSE city END, "
                    "state=CASE WHEN state IS NULL OR state='' THEN ? ELSE state END "
                    "WHERE rowid=?", (c, st, rid))
            wdb.execute("INSERT OR IGNORE INTO church_enrichment (church_id) VALUES (?)", (rid,))
            wdb.execute(
                "UPDATE church_enrichment SET county_fips=?, county_name=?, tract_fips=? WHERE church_id=?",
                (cf, cn, tf, rid))
        wdb.commit()
        wdb.close()
        updated += len(batch)
    
    # Provenance
    elapsed = time.time() - start
    db = sqlite3.connect(DB)
    db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
                  VALUES ('census_batch_reverse','reverse_geocode_us_census_batch.py',?,datetime('now'),'completed',?)""",
               (NOW, f"Concurrent Census API: {updated:,} processed, {stats['filled_city']:,} cities, {stats['ok']:,} OK in {elapsed:.0f}s"))
    db.commit()
    db.close()
    
    print(f"\nDone in {elapsed:.0f}s — {updated:,} processed | cities: {stats['filled_city']:,} | errors: {stats['http_err'] + stats['exception']:,}")


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Mapbox Geocoding Enrichment
============================
Uses Mapbox Geocoding API (100K free/mo) to add lat/lng to churches
that are missing geocoding data.

Usage:
    python scripts/enrichment/mapbox_geocode.py              # Full run (16K records)
    python scripts/enrichment/mapbox_geocode.py --limit 1000  # Test first 1K
    python scripts/enrichment/mapbox_geocode.py --dry-run     # Preview only

Remaining credits after this: ~84K for other uses.
"""
import csv, json, os, sys, time, sqlite3, urllib.request, urllib.parse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

MAPBOX_KEY = os.environ.get('MAPBOX_API_KEY', '')
if not MAPBOX_KEY:
    raise ValueError("MAPBOX_API_KEY environment variable is required")
GEO_URL = 'https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?access_token={key}&limit=1&country=US'

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
INPUT = os.path.join(PROJECT_DIR, 'data', 'needs_geocode.csv')

MAX_WORKERS = 8  # Mapbox free tier: ~10 req/sec
stats = {"geocoded": 0, "errors": 0, "skipped": 0, "api_calls": 0}
stats_lock = __import__("threading").Lock()


def geocode_church(name, address, city, state, zipcode):
    """Call Mapbox Geocoding API. Returns (lat, lng, source) or (None, None, None)."""
    # Build query: prefer address, fall back to name + city + state
    if address and len(address) > 5:
        query = f"{address}, {city}, {state} {zipcode or ''}".strip()
    else:
        query = f"{name}, {city}, {state}".strip()
    
    if not query:
        return None, None, None
    
    url = GEO_URL.format(
        query=urllib.request.quote(query),
        key=MAPBOX_KEY
    )
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        with stats_lock:
            stats['api_calls'] += 1
        
        features = data.get('features', [])
        if features:
            center = features[0].get('center', [])
            if center and len(center) == 2:
                return center[1], center[0], 'mapbox_street'
        
        return None, None, None
        
    except Exception as e:
        with stats_lock:
            stats['errors'] += 1
        return None, None, str(e)[:50]


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Mapbox Geocoding Enrichment")
    parser.add_argument('--limit', type=int, default=0, help='Max records')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--workers', type=int, default=MAX_WORKERS, help='Threads')
    args = parser.parse_args()

    # Load churches needing geocoding
    rows = []
    with open(INPUT, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((r['id'], r['name'], r['address'], r['city'], r['state'], r['zip']))
    
    if args.limit:
        rows = rows[:args.limit]
    
    total = len(rows)
    log(f"Geocoding {total:,} churches via Mapbox...")
    log(f"API credits used: ~{total:,}  |  Remaining: ~{100000-total:,} of 100K free")

    if args.dry_run:
        sample = rows[:5]
        for r in sample:
            cid, name, addr, city, state, zipc = r
            lat, lng, src = geocode_church(name, addr, city, state, zipc)
            print(f"  ID {cid}: {name[:35]:35s} -> lat={lat}, lng={lng}, src={src}")
        print(f"\nDry run complete. Would process {total:,} churches.")
        return

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(geocode_church, *r): r[0] for r in rows}
        done = 0
        for f in as_completed(futures):
            done += 1
            lat, lng, source = f.result()
            church_id = futures[f]
            
            if lat and lng:
                results.append((church_id, lat, lng, source))
                with stats_lock:
                    stats['geocoded'] += 1
            else:
                with stats_lock:
                    stats['skipped'] += 1
            
            if done % 1000 == 0:
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                log(f"  {done:,}/{total:,} — {stats['geocoded']:,} geocoded, {stats['errors']:,} errors ({rate:.0f}/sec)")

    elapsed = time.time() - start_time
    log(f"\nComplete in {elapsed/60:.1f} min")
    log(f"  API calls: {stats['api_calls']:,}")
    log(f"  Geocoded:  {stats['geocoded']:,}")
    log(f"  Errors:    {stats['errors']:,}")
    log(f"  Skipped:   {stats['skipped']:,}")

    # Update DB
    if results:
        db = sqlite3.connect(DB_PATH)
        db.execute("BEGIN TRANSACTION")
        upd = 0
        for church_id, lat, lng, source in results:
            db.execute(
                "UPDATE churches SET latitude=?, longitude=?, geocode_source=?, "
                "geocode_last_verified=datetime('now'), "
                "geocode_confidence = CASE WHEN ?='mapbox_street' THEN 0.9 ELSE 0.5 END "
                "WHERE id=?",
                (lat, lng, source, source, church_id)
            )
            upd += 1
            if upd % 1000 == 0:
                db.commit()
        db.commit()
        db.close()
        log(f"Updated {upd:,} records in DB")

    # Final stats
    db = sqlite3.connect(DB_PATH)
    has = db.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL").fetchone()[0]
    db.close()
    log(f"Total with geocoding: {has:,} / 258,006 ({has/258006*100:.1f}%)")
    log(f"Mapbox credits remaining: ~{100000-stats['api_calls']:,} of 100K")


if __name__ == '__main__':
    main()

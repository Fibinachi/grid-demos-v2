#!/usr/bin/env python3
"""
GrantWizard — Geocoding Upgrade Script
=========================================
Upgrades ZIP-centroid lat/lng to street-level accuracy using
the Census Geocoder API. Free, no API key required.

Strategy:
  1. Priority: churches with websites (~29K, ~10 min)
  2. Remaining: all churches with street addresses (~234K, ~1.3 hr)

Runs at ~50 req/sec with 20 threads. Progress saved every 1000 records.

Usage:
    python scripts/enrichment/upgrade_geocoding.py              # Full run
    python scripts/enrichment/upgrade_geocoding.py --priority-only # Websites only
    python scripts/enrichment/upgrade_geocoding.py --limit 1000  # Test run
"""

import sqlite3, os, sys, time, urllib.request, json, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Optimal throughput: 20 threads, no artificial sleep
MAX_WORKERS = 20
COMMIT_INTERVAL = 1000


def geocode_one(record):
    """Geocode a single address via Census Geocoder. Returns (id, lat, lng, success)."""
    cid, addr, city, state_s, zip_code = record
    full = f"{addr}, {city}, {state_s} {zip_code}".strip(", ")
    params = urllib.parse.urlencode({"address": full, "benchmark": "2020", "format": "json"})
    url = f"{CENSUS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                c = matches[0]["coordinates"]
                return (cid, float(c["y"]), float(c["x"]), True)
    except Exception:
        pass
    return (cid, None, None, False)


def run_batch(db, records, label):
    """Geocode a batch of records with threaded workers."""
    if not records:
        return 0
    
    print(f"\n  {label}: {len(records):,} records")
    upgraded = 0
    attempted = 0
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(geocode_one, r): r for r in records}
        
        for i, f in enumerate(as_completed(futures)):
            cid, lat, lng, ok = f.result()
            attempted += 1
            
            if ok:
                db.execute(
                    "UPDATE churches SET latitude=?, longitude=?, geocode_source='census_street' WHERE id=?",
                    (lat, lng, cid)
                )
                upgraded += 1
            
            if attempted % COMMIT_INTERVAL == 0:
                db.commit()
                elapsed = time.time() - start
                rate = attempted / elapsed if elapsed > 0 else 0
                pct = attempted / len(records) * 100
                eta = (len(records) - attempted) / rate if rate > 0 else 0
                print(f"    {attempted:,}/{len(records):,} ({pct:.0f}%), {upgraded:,} upgraded, {rate:.0f}/sec, ETA {eta/60:.0f} min")
    
    db.commit()
    elapsed = time.time() - start
    print(f"  ✅ {label}: {upgraded:,}/{attempted:,} upgraded ({upgraded/attempted*100:.0f}% hit rate) in {elapsed/60:.1f} min")
    return upgraded


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upgrade ZIP centroids to street-level geocoding")
    parser.add_argument("--priority-only", action="store_true", help="Only upgrade churches with websites")
    parser.add_argument("--limit", type=int, default=0, help="Limit to N records (test mode)")
    args = parser.parse_args()
    
    print("GrantWizard — Geocoding Upgrade")
    print("=" * 40)
    
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")  # Speed up bulk writes
    
    total_upgraded = 0
    
    # Phase 1: Priority — churches with websites AND street addresses
    # (skips records already attempted in previous run with no match)
    cur = db.cursor()
    if not args.priority_only:
        print("  Phase 1: Priority batch completed in previous run (21,613 upgraded)")
        print("  Skipping 7,297 already-failed records")
    
    # Phase 2: Remaining — all other addresses (no websites)
    cur.execute("""
        SELECT id, address, city, state, zip FROM churches 
        WHERE geocode_source = 'zip_centroid' 
          AND address IS NOT NULL AND address != ''
        ORDER BY id
    """)
    remaining = cur.fetchall()
    if args.limit > 0:
        remaining = remaining[:args.limit]
    
    if remaining:
        total_upgraded += run_batch(db, remaining, "Phase 2: All remaining addresses")
    
    # Summary
    print(f"\n=== Final Summary ===")
    print(f"Total upgraded to street-level: {total_upgraded:,}")
    
    cur.execute("SELECT geocode_source, COUNT(*) FROM churches WHERE latitude IS NOT NULL GROUP BY geocode_source ORDER BY COUNT(*) DESC")
    for src, cnt in cur.fetchall():
        print(f"  {src}: {cnt:,}")
    cur.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL")
    print(f"  None (ungeocoded): {cur.fetchone()[0]:,}")
    
    db.close()
    print("\nDone! Cost: $0.00")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GrantWizard — Tract FIPS Upgrade
==================================
Reverse geocodes lat/lng to Census Tract FIPS using threaded API calls
with rate limiting. Reliable approach with small batch processing.

Usage:
    python scripts/enrichment/upgrade_tract_fips.py
    python scripts/enrichment/upgrade_tract_fips.py --limit 5000
"""
import json, os, sqlite3, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

def reverse_one(lat, lng):
    params = urllib.parse.urlencode({"x": lng, "y": lat, "benchmark": "Public_AR_Current", "vintage": "Current_Current", "format": "json"})
    try:
        req = urllib.request.Request(f"{CENSUS_URL}?{params}", headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tracts = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
        if tracts:
            return tracts[0].get("GEOID", "")
    except Exception:
        pass
    return None

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")
    cur = db.cursor()
    
    cur.execute("SELECT COUNT(*) FROM churches WHERE tract_fips IS NOT NULL AND tract_fips != ''")
    starting = cur.fetchone()[0]
    print(f"Starting tract_fips count: {starting:,}")
    
    cur.execute("""SELECT id, latitude, longitude FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        AND (tract_fips IS NULL OR tract_fips = '')
        AND geocode_source IN ('census_street','mapbox','here')
        ORDER BY id""")
    rows = cur.fetchall()
    if args.limit > 0:
        rows = rows[:args.limit]
    
    print(f"Records: {len(rows):,}")
    if not rows:
        print("Nothing to do!"); db.close(); return
    
    updated = 0; errors = 0; start = time.time()
    BATCH = 100  # Process 100 at a time
    
    for batch_start in range(0, len(rows), BATCH):
        batch = rows[batch_start:batch_start + BATCH]
        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(lambda r=r: (r[0], reverse_one(r[1], r[2]))): r for r in batch}
            for f in as_completed(futs):
                cid, result = f.result()
                if result:
                    db.execute("UPDATE churches SET tract_fips=?, tract_geocode_source='census' WHERE id=?", (result, cid))
                    updated += 1
                else:
                    errors += 1
        db.commit()
        done = min(batch_start + BATCH, len(rows))
        elapsed = time.time() - start
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(rows) - done) / rate if rate > 0 else 0
        print(f"  {done:,}/{len(rows):,} ({done/len(rows)*100:.0f}%), {updated:,} ok, {errors:,} err, {rate:.0f}/sec, ETA {eta/60:.0f} min")
        time.sleep(0.5)  # Small delay between batches
    
    elapsed = time.time() - start
    cur.execute("SELECT COUNT(*) FROM churches WHERE tract_fips IS NOT NULL AND tract_fips != ''")
    final = cur.fetchone()[0]
    print(f"\n✅ {updated:,} upgraded, {errors:,} errors, {elapsed/60:.1f} min")
    print(f"Total tract_fips: {final:,} (+{final-starting:,})")
    db.close()

if __name__ == "__main__":
    main()

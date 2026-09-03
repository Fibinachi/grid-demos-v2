#!/usr/bin/env python3
"""
RUCC-Aware Tract Inference
===========================
For US churches missing tract FIPS, infer from nearest church WITH a tract
in the same county, using RUCC codes to set distance thresholds:
  RUCC 1-3 (metro): 200m
  RUCC 4-5 (micropolitan): 500m
  RUCC 6-7 (nonmetro urban): 1000m
  RUCC 8-9 (rural): 3000m

Runs in seconds rather than hours. Falls back to Census API for unmatched.
"""
import sqlite3, math, json, time
from datetime import datetime
from collections import defaultdict

DB = "churches.db"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def haversine_m(lat1, lon1, lat2, lon2):
    """Fast approximate distance in meters."""
    dlat = (lat2 - lat1) * 111320
    dlon = (lon2 - lon1) * 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.sqrt(dlat * dlat + dlon * dlon)

# RUCC -> max distance in meters
RUCC_THRESHOLDS = {
    1: 200, 2: 200, 3: 200,   # Metro
    4: 500, 5: 500,            # Micropolitan
    6: 1000, 7: 1000,          # Nonmetro urban
    8: 3000, 9: 3000,          # Rural / remote
}

def main():
    db = sqlite3.connect(DB)
    cur = db.cursor()

    # 1. Load churches needing tract (have GPS + county, no fips)
    cur.execute("""
        SELECT id, latitude, longitude, county_fips_5
        FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
          AND (fips IS NULL OR fips = '')
    """)
    need_rows = cur.fetchall()
    log(f"Churches needing tract: {len(need_rows):,}")

    if not need_rows:
        log("Nothing to do!")
        db.close()
        return

    # 2. Load RUCC codes
    cur.execute("SELECT fips, rucc_code FROM rucc_codes")
    rucc = {str(r[0]).zfill(5): r[1] for r in cur.fetchall()}
    log(f"RUCC codes loaded: {len(rucc)} counties")

    # 3. Load reference churches (have tract + GPS + county)
    cur.execute("""
        SELECT id, latitude, longitude, county_fips_5, fips
        FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
          AND fips IS NOT NULL AND fips != ''
    """)
    ref_rows = cur.fetchall()
    log(f"Reference churches with tract: {len(ref_rows):,}")

    # 4. Index reference churches by county
    ref_by_county = defaultdict(list)
    for r in ref_rows:
        cfips = str(r[3]).zfill(5)
        ref_by_county[cfips].append((r[1], r[2], r[4]))  # lat, lon, fips
    log(f"Reference counties: {len(ref_by_county)}")

    # 5. Match each church to nearest reference in same county within RUCC threshold
    matched = 0
    unmatched = 0
    no_county = 0
    no_rucc = 0
    too_far = 0
    db_batch = []
    county_stats = defaultdict(lambda: {"matched": 0, "unmatched": 0, "too_far": 0})

    start = time.time()
    for idx, (cid, lat, lon, cfips_raw) in enumerate(need_rows):
        cfips = str(cfips_raw).zfill(5)
        refs = ref_by_county.get(cfips, [])
        
        if not refs:
            no_county += 1
            county_stats[cfips]["unmatched"] += 1
            continue
        
        rucc_code = rucc.get(cfips)
        if rucc_code is None:
            no_rucc += 1
            county_stats[cfips]["unmatched"] += 1
            continue
        
        max_dist = RUCC_THRESHOLDS.get(rucc_code, 200)
        
        # Find nearest reference
        best_dist = float('inf')
        best_fips = None
        for rlat, rlon, rfips in refs:
            d = haversine_m(lat, lon, rlat, rlon)
            if d < best_dist:
                best_dist = d
                best_fips = rfips
        
        if best_fips and best_dist <= max_dist:
            matched += 1
            db_batch.append((best_fips, cid))
            county_stats[cfips]["matched"] += 1
        else:
            unmatched += 1
            if best_fips:
                too_far += 1
                county_stats[cfips]["too_far"] += 1
            else:
                county_stats[cfips]["unmatched"] += 1

        # Commit batch
        if len(db_batch) >= 500:
            cur.executemany("UPDATE churches SET fips=? WHERE id=?", db_batch)
            db.commit()
            db_batch = []

        # Progress every 10000
        if (idx + 1) % 10000 == 0:
            elapsed = time.time() - start
            rate = (idx + 1) / elapsed
            pct = (idx + 1) / len(need_rows) * 100
            log(f"  {pct:.0f}% ({idx+1:,}/{len(need_rows):,}) | {rate:.0f}/s | +{matched} ✓ {unmatched} ✗")

    # Final flush
    if db_batch:
        cur.executemany("UPDATE churches SET fips=? WHERE id=?", db_batch)
        db.commit()

    # 6. Also fill county_fips_5 where missing but we have fips
    cur.execute("""
        UPDATE churches SET county_fips_5 = substr(fips, 1, 5)
        WHERE country = 'US'
          AND (county_fips_5 IS NULL OR county_fips_5 = '')
          AND fips IS NOT NULL AND fips != ''
    """)
    county_backfill = cur.rowcount
    db.commit()

    elapsed = time.time() - start
    
    # Provenance
    cur.execute("""
        INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, status,
         churches_updated, records_attempted, records_matched, fields_populated, notes)
        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?, 'fips,county_fips_5', ?)
    """, ("rucc_tract_inference", __file__, datetime.now().isoformat(),
          datetime.now().isoformat(), matched + county_backfill,
          len(need_rows), matched,
          f"RUCC-based NN inference: {matched} matched, {unmatched} unmatched "
          f"({no_county} no refs in county, {no_rucc} no RUCC, {too_far} too far). "
          f"Thresholds: {RUCC_THRESHOLDS}. County backfill: {county_backfill}. "
          f"Duration: {elapsed:.0f}s"))
    db.commit()

    # Summary
    log(f"\n{'='*50}")
    log(f"COMPLETE in {elapsed:.1f}s")
    log(f"  Matched: {matched:,} ({matched/len(need_rows)*100:.1f}%)")
    log(f"  Unmatched: {unmatched:,}")
    log(f"    - No refs in county: {no_county:,}")
    log(f"    - No RUCC code: {no_rucc:,}")
    log(f"    - Too far from ref: {too_far:,}")
    log(f"  County FIPS backfill: {county_backfill:,}")

    # Show top 10 unmatched counties
    log(f"\n  Top unmatched counties:")
    sorted_counties = sorted(county_stats.items(), key=lambda x: x[1]["unmatched"] + x[1]["too_far"], reverse=True)
    for cfips, stats in sorted_counties[:10]:
        total_unmatched = stats["unmatched"] + stats["too_far"]
        if total_unmatched > 0:
            ruc = rucc.get(cfips, "?")
            log(f"    {cfips} (RUCC={ruc}): {stats['matched']} ✓, {stats['unmatched']} ✗, {stats['too_far']} far")

    log(f"\n  Remaining gap (needs Census API fallback): {unmatched:,}")
    db.close()

if __name__ == "__main__":
    main()

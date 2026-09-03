#!/usr/bin/env python3
"""
Census Tract Geolocation Backfill (Threaded)
=============================================
Takes US churches with lat/lng but no FIPS code, queries the Census
single-coordinate Geocoder API via threaded workers, and stores tract FIPS.

The Census coordinatesbatch POST endpoint returns 500 — single GET works.
See /memories/repo/census-api.md for API details.

Usage:
    python scripts/enrichment/geocode_tracts.py                  # Full run
    python scripts/enrichment/geocode_tracts.py --dry-run        # Preview
    python scripts/enrichment/geocode_tracts.py --limit 2000     # Test run
"""
import sqlite3, os, sys, json, urllib.request, ssl, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "churches.db")
WORKERS = 8
DB_BATCH = 400
CHECKPOINT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "geocode_tracts_checkpoint.json")

# SSL workaround for Census API certificate issues
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

API = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"processed": 0, "updated": 0, "failed": 0}

def save_checkpoint(processed, updated, failed):
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    with open(CHECKPOINT, "w") as f:
        json.dump({"processed": processed, "updated": updated, "failed": failed,
                   "last": datetime.now().isoformat()}, f)

def geocode_single(church_id, lat, lon):
    """Query single-coordinate Census API. Returns (church_id, tract_fips, county_fips) or Nones."""
    url = f"{API}?x={lon}&y={lat}&benchmark=4&vintage=Current_Current&format=json"
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(r, timeout=30, context=SSL_CTX) as f:
            data = json.loads(f.read().decode())
        tracts = data.get("result", {}).get("geographies", {}).get("Census Tracts", [])
        if tracts:
            geo = tracts[0]
            return (church_id, geo.get("GEOID", ""), geo.get("COUNTY", ""))
    except:
        pass
    return (church_id, None, None)

def progress_bar(n, total, width=50):
    pct = n / total if total else 0
    filled = int(width * pct)
    bar = "=" * filled + "-" * (width - filled)
    return f"[{bar}] {pct*100:.1f}% ({n:,}/{total:,})"

def main():
    dry_run = "--dry-run" in sys.argv
    limit = 0
    for a in sys.argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    query = """
        SELECT id, latitude, longitude FROM churches 
        WHERE country = 'US'
          AND latitude IS NOT NULL AND latitude != 0
          AND longitude IS NOT NULL AND longitude != 0
          AND (fips IS NULL OR fips = '')
        ORDER BY id
    """
    if limit:
        query += f" LIMIT {limit}"

    cur.execute(query)
    rows = cur.fetchall()
    total = len(rows)

    log(f"Churches needing FIPS: {total:,}")

    if dry_run:
        log(f"  DRY RUN — would process {total:,} records ({WORKERS} threads, batch={DB_BATCH})")
        for r in rows[:5]:
            log(f"    ID={r[0]} lat={r[1]:.4f} lon={r[2]:.4f}")
        db.close()
        return

    # Checkpoint
    cp = load_checkpoint()
    start_idx = cp["processed"]
    if start_idx > 0:
        log(f"Resuming from checkpoint: {start_idx:,} / {total:,}")
    rows = rows[start_idx:]

    # Provenance
    started_at = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, status, records_attempted, fields_populated, parameters)
        VALUES (?, ?, ?, 'running', ?, ?, ?)
    """, ("census_geocoder", "geocode_tracts", started_at, total,
          "fips,county_fips_5",
          json.dumps({"api": API, "workers": WORKERS, "db_batch": DB_BATCH})))
    log_id = cur.lastrowid
    db.commit()

    updated = cp["updated"]
    failed = cp["failed"]
    db_batch = []
    start_time = time.time()

    log(f"Starting {WORKERS} threads for {len(rows):,} records...")

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        for chunk_start in range(0, len(rows), DB_BATCH):
            chunk = rows[chunk_start:chunk_start + DB_BATCH]
            futures = {executor.submit(geocode_single, r[0], r[1], r[2]): r for r in chunk}

            for future in as_completed(futures):
                cid, tract, county = future.result()
                if tract:
                    updated += 1
                    db_batch.append((tract, county or "", cid))
                else:
                    failed += 1

            if len(db_batch) >= DB_BATCH:
                cur.executemany("UPDATE churches SET fips=?, county_fips_5=? WHERE id=?", db_batch)
                db.commit()
                db_batch = []

            processed = start_idx + chunk_start + len(chunk)
            elapsed = max(time.time() - start_time, 0.1)
            rate = processed / elapsed
            eta_sec = (total - processed) / rate if rate > 0 else 0
            log(f"  {progress_bar(processed, total)} | {rate:.0f}/s | ETA: {eta_sec/60:.0f}m | +{updated}/{failed}")
            save_checkpoint(processed, updated, failed)

    if db_batch:
        cur.executemany("UPDATE churches SET fips=?, county_fips_5=? WHERE id=?", db_batch)
        db.commit()

    elapsed = time.time() - start_time
    completed_at = datetime.now().isoformat()
    cur.execute("""
        UPDATE provenance_log SET status='completed', completed_at=?,
            churches_updated=?, records_matched=?, notes=?
        WHERE id=?
    """, (completed_at, updated, updated,
          f"{updated} tracts, {failed} failed, {elapsed/60:.0f}m, {total/elapsed:.0f}/s", log_id))
    db.commit()

    log(f"\nCompleted in {elapsed/60:.1f}m — {updated:,} found, {failed:,} failed ({updated/total*100:.1f}%)")
    db.close()

if __name__ == "__main__":
    main()

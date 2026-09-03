"""
Fetch per-church elevation from Open-Meteo Elevation API for TX Hill Country.

Open-Meteo allows up to 100 lat/lon pairs per request.
Replaces county-level elevation_m with actual per-point DEM elevation.

Usage:
    python scripts/enrichment/fetch_dem_elevation_tx.py
"""

import sqlite3
import time
import urllib.request
import json

DB_PATH = "E:/grid/churches.db"
BATCH_SIZE = 100
SLEEP_BETWEEN = 1.0  # seconds between API calls (avoid 429 rate limiting)
MAX_RETRIES = 3

COUNTIES = ['Kerr','Kendall','Uvalde','Bandera','Gillespie','Medina','Real','Edwards','Comal','Blanco','Hays','Kimble']
PLACEHOLDERS = ','.join('?' * len(COUNTIES))

print("=" * 60)
print("FETCH PER-CHURCH ELEVATION FROM OPEN-METEO DEM")
print("=" * 60)

# Load churches needing elevation
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

rows = db.execute(f"""
    SELECT rowid, latitude, longitude, elevation_m AS old_elevation, name, city, county
    FROM churches
    WHERE state='TX'
      AND county IN ({PLACEHOLDERS})
      AND latitude IS NOT NULL
      AND longitude IS NOT NULL
    ORDER BY rowid
""", COUNTIES).fetchall()

print(f"\nChurches to process: {len(rows):,}")

# Build batches
batches = []
for i in range(0, len(rows), BATCH_SIZE):
    batches.append(rows[i:i + BATCH_SIZE])

print(f"Batches: {len(batches)} (max {BATCH_SIZE} per request)")
print(f"Estimated time: {len(batches) * SLEEP_BETWEEN:.0f}s\n")

# Fetch elevation for each batch
results = {}  # rowid -> elevation_m
failures = 0

for batch_idx, batch in enumerate(batches):
    # Build comma-separated lat,lon pairs
    coords = []
    for r in batch:
        coords.append(f"{r['latitude']:.6f}")
        coords.append(f"{r['longitude']:.6f}")

    # Open-Meteo Elevation API: /v1/elevation?latitude=LAT,LAT,...&longitude=LON,LON,...
    lat_str = ','.join(coords[0::2])
    lon_str = ','.join(coords[1::2])

    url = f"https://api.open-meteo.com/v1/elevation?latitude={lat_str}&longitude={lon_str}"

    success = False
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            if 'elevation' in data:
                elevations = data['elevation']
                for r, elev in zip(batch, elevations):
                    results[r['rowid']] = round(elev, 1)
                success = True
            else:
                print(f"\n  [FAIL] Batch {batch_idx+1}: unexpected response {str(data)[:100]}")
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 2
                print(f"\r  Retry batch {batch_idx+1} in {wait}s (attempt {attempt+2}/{MAX_RETRIES})...", end='', flush=True)
                time.sleep(wait)
            else:
                print(f"\n  [FAIL] Batch {batch_idx+1} after {MAX_RETRIES} attempts: {e}")
                failures += len(batch)

    if not success and attempt >= MAX_RETRIES - 1:
        pass  # already counted as failure

    print(f"\rFetching elevation: {batch_idx+1}/{len(batches)} batches ({((batch_idx+1)/len(batches)*100):.0f}%)", end='', flush=True)
    time.sleep(SLEEP_BETWEEN)

print(f"\nResults: {len(results):,} elevations fetched, {failures} failures")

if failures > 0:
    print(f"\n[WARN] {failures} churches failed - these will keep old county-level elevation")

# Update churches table
print("\nUpdating churches.elevation_m with per-point DEM data...")
db.execute("BEGIN")
updated = 0
for rowid, elev in results.items():
    old = db.execute("SELECT elevation_m FROM churches WHERE rowid=?", (rowid,)).fetchone()
    old_val = old[0] if old else None
    if old_val is None or abs(old_val - elev) > 0.01:
        db.execute("UPDATE churches SET elevation_m=? WHERE rowid=?", (elev, rowid))
        updated += 1

db.commit()
print(f"   {updated:,} churches updated with per-point elevation")

# Log provenance
try:
    from gw_db import connect
    gw = connect()
    gw.log_provenance(
        source="open-meteo-elevation-api",
        description=f"Fetched per-church DEM elevation for {len(COUNTIES)} TX Hill Country counties ({len(results)} churches)",
        row_count=updated
    )
except Exception as e:
    print(f"   [WARN] Could not log provenance: {e}")

# Summary stats
print("\nNew elevation distribution by county:")
for county in COUNTIES:
    stats = db.execute("""
        SELECT COUNT(*), ROUND(MIN(elevation_m),0), ROUND(MAX(elevation_m),0), ROUND(AVG(elevation_m),0)
        FROM churches 
        WHERE state='TX' AND county=? AND elevation_m IS NOT NULL
    """, (county,)).fetchone()
    if stats[0] > 0:
        unique_count = db.execute(
            "SELECT COUNT(DISTINCT elevation_m) FROM churches WHERE state='TX' AND county=? AND elevation_m IS NOT NULL",
            (county,)
        ).fetchone()[0]
        print(f"  {county:12s}: {stats[0]:>4,} churches | range {int(stats[1]):>5,}-{int(stats[2]):>5,}m | avg {int(stats[3]):>5,}m | {unique_count} unique values")

db.close()
print("\nDone.")

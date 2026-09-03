"""
Step 2+3: Download OSM places of worship from BQ → merge locally into holy_sites.

Pattern: Download from BQ → build local grid index → match → UPDATE SQLite.
Matches holy_sites records to OSM by spatial proximity (25m tolerance).
Populates: osm_id, osm_type, osm_version, osm_timestamp.
"""
import os, sys, time, math, csv, sqlite3, tempfile
from datetime import datetime, timezone

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

DB = "E:/grid/churches.db"
PROJECT = 'american-rel-infra'
NOW = datetime.now(timezone.utc).isoformat()
t0 = time.time()

MATCH_DISTANCE_M = 25.0
GRID_RES = 100  # 0.01 degree ≈ 1.1km grid cells

def log(msg):
    print(f"[{time.time()-t0:7.1f}s] {msg}", flush=True)

def haversine_m(lat1, lon1, lat2, lon2):
    """Fast haversine distance in meters"""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ── Step 1: Count holy_sites needing OSM enrichment ──
log("Step 1: Counting holy_sites needing OSM enrichment...")
db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")

to_enrich = db.execute("""
    SELECT COUNT(*) FROM holy_sites 
    WHERE source_primary = 'overture' 
      AND lat IS NOT NULL AND lon IS NOT NULL
      AND osm_id IS NULL
""").fetchone()[0]
log(f"  {to_enrich:,} overture records need OSM enrichment")

if to_enrich == 0:
    log("  Nothing to do!")
    db.close()
    sys.exit(0)

# ── Step 2: Download OSM places of worship from BQ ──
log("\nStep 2: Downloading OSM places of worship from BigQuery...")
client = bigquery.Client(project=PROJECT)

osm_file = os.path.join(tempfile.gettempdir(), 'osm_pow_export.csv')
osm_count = 0

sql = """
SELECT osm_type, osm_id, osm_version, osm_timestamp, lat, lon
FROM (
    SELECT 'node' as osm_type, osm_id, osm_version, osm_timestamp,
           ST_Y(geometry) as lat, ST_X(geometry) as lon
    FROM bigquery-public-data.geo_openstreetmap.planet_features_points
    WHERE ('amenity', 'place_of_worship') IN (SELECT (key, value) FROM UNNEST(all_tags))
      AND osm_id IS NOT NULL
    
    UNION ALL
    
    SELECT 'way' as osm_type, osm_id, osm_version, osm_timestamp,
           ST_Y(ST_CENTROID(geometry)) as lat, ST_X(ST_CENTROID(geometry)) as lon
    FROM bigquery-public-data.geo_openstreetmap.planet_features_multipolygons
    WHERE ('amenity', 'place_of_worship') IN (SELECT (key, value) FROM UNNEST(all_tags))
      AND osm_id IS NOT NULL
)
WHERE lat IS NOT NULL AND lon IS NOT NULL
  AND lat != 0 AND lon != 0
"""

with open(osm_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['osm_type', 'osm_id', 'osm_version', 'osm_timestamp', 'lat', 'lon'])
    
    job = client.query(sql)
    for row in job.result():
        writer.writerow([
            row[0],            # osm_type
            int(row[1]),       # osm_id
            int(row[2]),       # osm_version
            str(row[3]),       # osm_timestamp
            round(float(row[4]), 6),
            round(float(row[5]), 6),
        ])
        osm_count += 1
        if osm_count % 200000 == 0:
            log(f"  Downloaded {osm_count:,} OSM records...")

log(f"  Total OSM records: {osm_count:,}")
log(f"  File: {osm_file} ({os.path.getsize(osm_file)/1024/1024:.1f} MB)")

# ── Step 3: Build grid index ──
log("\nStep 3: Building grid index...")
grid = {}

with open(osm_file, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        lat = float(row['lat'])
        lon = float(row['lon'])
        gx = int(lat * GRID_RES)
        gy = int(lon * GRID_RES)
        key = (gx, gy)
        if key not in grid:
            grid[key] = []
        grid[key].append((
            row['osm_type'],
            int(row['osm_id']),
            int(row['osm_version']),
            row['osm_timestamp'],
            lat, lon
        ))

log(f"  Grid cells: {len(grid):,} (avg {osm_count/max(len(grid),1):.1f} records/cell)")

# ── Step 4: Match holy_sites → OSM ──
log(f"\nStep 4: Matching {to_enrich:,} holy_sites to OSM...")
db.row_factory = sqlite3.Row
rows = db.execute("""
    SELECT site_id, overture_id, lat, lon, name
    FROM holy_sites 
    WHERE source_primary = 'overture' 
      AND lat IS NOT NULL AND lon IS NOT NULL
      AND osm_id IS NULL
    ORDER BY site_id
""").fetchall()
log(f"  Fetched {len(rows):,} holy_sites")

updates = []
matched = 0
no_cell = 0
too_far = 0

for i, row in enumerate(rows):
    if i % 100000 == 0 and i > 0:
        log(f"  Processed {i:,}/{len(rows):,} (matched {matched:,})")
    
    lat, lon = row['lat'], row['lon']
    gx = int(lat * GRID_RES)
    gy = int(lon * GRID_RES)
    
    candidates = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cell = grid.get((gx + dx, gy + dy))
            if cell:
                candidates.extend(cell)
    
    if not candidates:
        no_cell += 1
        continue
    
    best_dist = MATCH_DISTANCE_M + 1
    best = None
    for c in candidates:
        d = haversine_m(lat, lon, c[4], c[5])
        if d < best_dist:
            best_dist = d
            best = c
    
    if best and best_dist <= MATCH_DISTANCE_M:
        updates.append((best[1], best[0], best[2], best[3], row['site_id']))
        matched += 1
    else:
        too_far += 1

log(f"  Matched: {matched:,}")
log(f"  No grid cell: {no_cell:,}")
log(f"  Too far (> {MATCH_DISTANCE_M}m): {too_far:,}")
log(f"  Match rate: {100*matched/max(len(rows),1):.1f}%")

# ── Step 5: UPDATE holy_sites (with retry for lock contention) ──
log("\nStep 5: Updating holy_sites...")
db.row_factory = None
batch_size = 5000

# Save updates to temp file so we can resume
updates_file = os.path.join(tempfile.gettempdir(), 'osm_updates.csv')
with open(updates_file, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['osm_id', 'osm_type', 'osm_version', 'osm_timestamp', 'site_id'])
    writer.writerows(updates)
log(f"  Saved {len(updates):,} updates to {updates_file}")

for start in range(0, len(updates), batch_size):
    batch = updates[start:start + batch_size]
    for attempt in range(5):
        try:
            db.execute("BEGIN")
            db.executemany("""
                UPDATE holy_sites 
                SET osm_id = ?, osm_type = ?, osm_version = ?, osm_timestamp = ?
                WHERE site_id = ?
            """, batch)
            db.commit()
            break
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(2 ** attempt)
                db.rollback()
            else:
                raise
    if start % 200000 == 0:
        log(f"  {start:,}/{len(updates):,} updated...")

log(f"  Total updated: {len(updates):,}")

# ── Step 6: Verify ──
log("\nStep 6: Verification...")
now_osm = db.execute("""
    SELECT COUNT(*) FROM holy_sites 
    WHERE source_primary = 'overture' AND osm_id IS NOT NULL
""").fetchone()[0]
log(f"  overture records with osm_id: {now_osm:,}")

log("\n  Sample:")
for r in db.execute("""
    SELECT osm_type, osm_id, osm_version, osm_timestamp, name, country
    FROM holy_sites 
    WHERE source_primary = 'overture' AND osm_id IS NOT NULL 
    LIMIT 8
"""):
    log(f"    osm_{r[0]}={r[1]} v{r[2]} {str(r[3])[:19]} {str(r[4])[:40]} {r[5]}")

# ── Step 7: Provenance ──
db.execute("""INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)""", (
    "osm_enrichment", "enrich_osm_ids.py", NOW,
    datetime.now(timezone.utc).isoformat(), 0,
    "osm_id,osm_type,osm_version,osm_timestamp",
    len(rows), matched,
    f"OSM ID enrichment via BQ geo_openstreetmap → local merge. "
    f"Matched {matched:,}/{len(rows):,} ({100*matched/max(len(rows),1):.1f}%) "
    f"at {MATCH_DISTANCE_M}m. Downloaded {osm_count:,} OSM places of worship."
))
db.commit()
db.close()

try:
    os.remove(osm_file)
except:
    pass

total = time.time() - t0
log(f"\n{'='*60}")
log(f"DONE in {total:.0f}s — {matched:,} records enriched with OSM IDs")

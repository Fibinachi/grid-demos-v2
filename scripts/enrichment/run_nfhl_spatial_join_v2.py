"""
NFHL Spatial Join v2 — BBOX-first with STRtree.
Pre-computed bounding boxes (compute_nfhl_bboxes.py) enable fast R-tree queries.
Only deserializes WKB for polygons whose bbox contains the church point.
"""
import sqlite3, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"
WORK_DB = PROJECT / "churches_nfhl_work.db"

SFHA_ZONES = {"A", "AE", "AH", "AO", "V", "VE", "D"}
ZONE_SEVERITY = {"V": 10, "VE": 10, "A": 8, "AE": 8, "AH": 8, "AO": 8, "D": 5, "A99": 8, "X": 0}
CHUNK_SIZE = 500
MAX_WKB_DESERIALIZE = 100_000

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i+1)/elapsed
    eta = (total-i-1)/rate/60 if rate>0 else 0
    pct = (i+1)/total*100
    f = int(30*(i+1)/total)
    print(f"\r    {'\u2588'*f}{'\u2591'*(30-f)} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)


print("=== NFHL SPATIAL JOIN v2 (BBOX + STRtree) ===\n")

# Step 1: Load bboxes + WKB references
print("Step 1: Loading bounding boxes and WKB references...")
db_read = sqlite3.connect(str(WORK_DB), timeout=60)
db_read.execute("PRAGMA query_only=ON")

t0 = time.time()
bbox_geoms = []
zone_data = []
rows = db_read.execute("""
    SELECT min_lon, min_lat, max_lon, max_lat, fld_zone, zone_subty, sfha_tf, geom_wkb
    FROM nfhl_flood_zones
    WHERE min_lon IS NOT NULL
""").fetchall()

from shapely.geometry import box, Point

for i, row in enumerate(rows):
    bbox_geoms.append(box(row[0], row[1], row[2], row[3]))
    zone_data.append((row[4], row[5], row[6], row[7]))
    if (i+1) % 100000 == 0:
        progress_bar(i+1, len(rows), t0, "")

progress_bar(len(rows), len(rows), t0, "")
print()
db_read.close()
print(f"  {len(rows):,} bboxes loaded in {time.time()-t0:.0f}s")

# Step 2: Build STRtree on bbox rectangles
print("\nStep 2: Building STRtree on bbox rectangles...")
t0 = time.time()
from shapely.strtree import STRtree
tree = STRtree(bbox_geoms)
print(f"  STRtree built with {len(bbox_geoms):,} bboxes in {time.time()-t0:.0f}s")

# Step 3: Load US churches
print("\nStep 3: Loading US church coordinates...")
db_read2 = sqlite3.connect(str(DB_PATH), timeout=120)
db_read2.execute("PRAGMA query_only=ON")
churches = list(db_read2.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    WHERE c.country='US' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
      AND c.latitude != '' AND c.longitude != ''
""").fetchall())
db_read2.close()
print(f"  {len(churches):,} US churches with GPS")

# Step 4: STRtree spatial join
print("\nStep 4: STRtree classification (bbox pre-filter + lazy WKB)...")
print("  (Only deserializing WKB when bbox contains the church)")
t0 = time.time()
results = []
in_sfha, zone_x, wkb_deserialized = 0, 0, 0
no_candidates = 0

from shapely import wkb as shapely_wkb

for i in range(0, len(churches), CHUNK_SIZE):
    batch = churches[i:i+CHUNK_SIZE]
    
    for church_id, lat, lon in batch:
        point = Point(lon, lat)
        candidates = tree.query(point)
        
        if len(candidates) == 0:
            results.append(("X", None, "F", church_id))
            zone_x += 1
            no_candidates += 1
            continue
        
        best_z, best_s, best_f = None, None, None
        best_severity = -1
        
        for idx in candidates:
            wkb_deserialized += 1
            wkb = zone_data[idx][3]
            
            if len(wkb) > MAX_WKB_DESERIALIZE:
                z, s, sfha = zone_data[idx][:3]
                sev = ZONE_SEVERITY.get(z, 0)
                if sev > best_severity:
                    best_z, best_s, best_f = z, s, sfha
                    best_severity = sev
                continue
            
            try:
                geom = shapely_wkb.loads(wkb)
                if geom.contains(point):
                    z, s, sfha = zone_data[idx][:3]
                    sev = ZONE_SEVERITY.get(z, 0)
                    if sev > best_severity:
                        best_z, best_s, best_f = z, s, sfha
                        best_severity = sev
            except Exception:
                pass
        
        if best_z:
            results.append((best_z, best_s, best_f, church_id))
            in_sfha += 1
        else:
            results.append(("X", None, "F", church_id))
            zone_x += 1
    
    progress_bar(i+len(batch), len(churches), t0,
                 f"SFHA={in_sfha:,} X={zone_x:,} deser={wkb_deserialized:,} no_cand={no_candidates:,}")

elapsed = time.time() - t0
total = in_sfha + zone_x
print(f"\n\nClassification: {total:,} churches in {elapsed/60:.1f}m ({total/elapsed:.0f} rec/s)")
print(f"  WKB deserializations: {wkb_deserialized:,} (avg {wkb_deserialized/total:.1f} per church)")
print(f"  Churches with no bbox candidates: {no_candidates:,} ({no_candidates/total*100:.1f}%)")

# Step 5: Write results to main DB
print("\nStep 5: Writing results to church_enrichment...")
db_write = sqlite3.connect(str(DB_PATH), timeout=120)
db_write.execute("PRAGMA journal_mode=WAL")
db_write.execute("PRAGMA synchronous=OFF")

cols = [c[1] for c in db_write.execute("PRAGMA table_info(church_enrichment)").fetchall()]
for col in ["fema_flood_zone", "fema_flood_zone_subty", "fema_sfha", "fema_flood_updated"]:
    if col not in cols:
        db_write.execute(f"ALTER TABLE church_enrichment ADD COLUMN {col} TEXT")
db_write.commit()

db_write.execute("""
    INSERT OR IGNORE INTO church_enrichment (church_id)
    SELECT id FROM churches WHERE country='US' AND latitude IS NOT NULL
""")
db_write.commit()

t0 = time.time()
for i in range(0, len(results), CHUNK_SIZE):
    batch = results[i:i+CHUNK_SIZE]
    for zone, subty, sfha, cid in batch:
        db_write.execute("""
            UPDATE church_enrichment
            SET fema_flood_zone = ?, fema_flood_zone_subty = ?,
                fema_sfha = ?, fema_flood_updated = datetime('now')
            WHERE church_id = ?
        """, (zone, subty, sfha, cid))
    db_write.commit()
    progress_bar(i+len(batch), len(results), t0, "writing")

db_write.close()
print(f"\n  Write complete in {time.time()-t0:.0f}s")

# Summary from work DB
print("\n=== FEMA FLOOD ZONE DISTRIBUTION ===")
db_summary = sqlite3.connect(str(DB_PATH), timeout=60)
db_summary.execute("PRAGMA query_only=ON")
for row in db_summary.execute("""
    SELECT fema_flood_zone,
           CASE WHEN fema_flood_zone IN ('A','AE','AH','AO','V','VE','D') THEN '[SFHA]' ELSE '' END,
           COUNT(*)
    FROM church_enrichment WHERE fema_flood_zone IS NOT NULL
    GROUP BY 1 ORDER BY 3 DESC
""").fetchall():
    print(f"  Zone {row[0]:5s} {row[1]:7s}: {row[2]:>10,}")

r = db_summary.execute("SELECT COUNT(*) FROM church_enrichment WHERE fema_flood_zone='X'").fetchone()
pct = r[0]/total*100 if total else 0
print(f"\n  HIGH GROUND (Zone X, minimal risk): {r[0]:,} ({pct:.1f}%)")
print(f"  IN FLOOD ZONE (SFHA): {total-r[0]:,} ({100-pct:.1f}%)")

print("\n--- TOP 10 STATES: HIGHEST % HIGH GROUND ---")
for row in db_summary.execute("""
    SELECT c.state,
           COUNT(*) as total,
           SUM(CASE WHEN ce.fema_flood_zone='X' THEN 1 ELSE 0 END) as safe,
           ROUND(100.0*SUM(CASE WHEN ce.fema_flood_zone='X' THEN 1 ELSE 0 END)/COUNT(*), 1) as safe_pct
    FROM churches c
    JOIN church_enrichment ce ON c.id = ce.church_id
    WHERE c.country='US' AND ce.fema_flood_zone IS NOT NULL
    GROUP BY c.state HAVING total >= 100
    ORDER BY safe_pct DESC LIMIT 10
""").fetchall():
    print(f"  {row[0]:4s}: {row[1]:>7,} churches, {row[2]:>7,} safe ({row[3]:.1f}%)")

print("\n--- TOP 10 STATES: LOWEST % HIGH GROUND (most at risk) ---")
for row in db_summary.execute("""
    SELECT c.state,
           COUNT(*) as total,
           SUM(CASE WHEN ce.fema_flood_zone='X' THEN 1 ELSE 0 END) as safe,
           ROUND(100.0*SUM(CASE WHEN ce.fema_flood_zone='X' THEN 1 ELSE 0 END)/COUNT(*), 1) as safe_pct
    FROM churches c
    JOIN church_enrichment ce ON c.id = ce.church_id
    WHERE c.country='US' AND ce.fema_flood_zone IS NOT NULL
    GROUP BY c.state HAVING total >= 100
    ORDER BY safe_pct ASC LIMIT 10
""").fetchall():
    print(f"  {row[0]:4s}: {row[1]:>7,} churches, {row[2]:>7,} safe ({row[3]:.1f}%)")

db_summary.close()
print("\nDone.")

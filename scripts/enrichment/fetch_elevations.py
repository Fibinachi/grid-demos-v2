"""
Step 2: Fetch elevations for US tract centroids and churches via Open-Meteo.
Checkpointed — can resume if interrupted.
Stores results in church_elevation and tract_elevation tables.
"""
import sqlite3, requests, time, sys, os
from datetime import datetime

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

BATCH_SIZE = 100  # 100 coords per API call
DELAY = 10.0      # seconds between calls: 6 calls/min × 100 = 600 coords/min (safe under limit)

# ── Create tables ──
db.executescript("""
    CREATE TABLE IF NOT EXISTS church_elevation (
        church_id INTEGER PRIMARY KEY,
        elevation_m REAL NOT NULL,
        source TEXT DEFAULT 'open-meteo',
        fetched_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tract_elevation (
        tract_fips TEXT PRIMARY KEY,
        elevation_m REAL NOT NULL,
        source TEXT DEFAULT 'open-meteo',
        fetched_at TEXT
    );
""")
db.commit()

def progress_bar(current, total, label="", width=40, start_time=None):
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    line = f"\r{label} [{bar}] {current:,}/{total:,} ({pct*100:.1f}%)"
    if start_time and current > 0:
        elapsed = time.time() - start_time
        rate = current / elapsed if elapsed > 0 else 0
        eta = (total - current) / rate if rate > 0 else 0
        line += f" | {rate:.0f}/s | ETA {eta/60:.0f}min"
    return line

def fetch_elevation_batch(coords, label="", max_retries=3):
    """coords = [(lat, lon, id), ...]. Returns [(id, elevation), ...]"""
    lats = ",".join(str(c[0]) for c in coords)
    lons = ",".join(str(c[1]) for c in coords)
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}",
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                elevations = data.get('elevation', [])
                if len(elevations) == len(coords):
                    return [(coords[i][2], elevations[i]) for i in range(len(coords))]
            elif resp.status_code == 429:
                wait = 60  # Wait full minute for rate limit reset
                print(f"\n  Rate limited at {fetched:,}, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(1)
        except Exception as e:
            time.sleep(2)
    return []

# ── PHASE 1: Tract centroid elevations ──
print("=== PHASE 1: Tract Centroid Elevations ===\n")

# Get tracts that need elevation
needed = db.execute("""
    SELECT t.tract_fips, t.intpt_lat, t.intpt_lon 
    FROM tract_centroids_us t
    LEFT JOIN tract_elevation te ON t.tract_fips = te.tract_fips
    WHERE te.tract_fips IS NULL
""").fetchall()

print(f"Tracts needing elevation: {len(needed):,}")

if needed:
    now = datetime.now().isoformat()
    fetched = 0
    total = len(needed)
    t0 = time.time()
    
    for i in range(0, total, BATCH_SIZE):
        batch = needed[i:i+BATCH_SIZE]
        coords = [(r[1], r[2], r[0]) for r in batch]
        
        results = fetch_elevation_batch(coords, "tracts")
        
        for tract_fips, elevation in results:
            db.execute("""
                INSERT OR REPLACE INTO tract_elevation (tract_fips, elevation_m, source, fetched_at)
                VALUES (?, ?, 'open-meteo', ?)
            """, (tract_fips, elevation, now))
        
        fetched += len(results)
        if i % 5000 == 0 or i + BATCH_SIZE >= total:
            db.commit()
        
        sys.stdout.write(progress_bar(fetched, total, "  Tracts", start_time=t0))
        sys.stdout.flush()
        time.sleep(DELAY)
    
    db.commit()
    print(f"\n  Done: {fetched:,} tract elevations\n")

# ── PHASE 2: US Church elevations ──
print("=== PHASE 2: US Church Elevations ===\n")

# Get US churches that need elevation
needed = db.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'US' 
    AND c.latitude IS NOT NULL 
    AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""").fetchall()

print(f"US churches needing elevation: {len(needed):,}")

if needed:
    now = datetime.now().isoformat()
    fetched = 0
    total = len(needed)
    t0 = time.time()
    
    for i in range(0, total, BATCH_SIZE):
        batch = needed[i:i+BATCH_SIZE]
        coords = [(r[1], r[2], r[0]) for r in batch]
        
        results = fetch_elevation_batch(coords, "churches")
        
        for church_id, elevation in results:
            db.execute("""
                INSERT OR REPLACE INTO church_elevation (church_id, elevation_m, source, fetched_at)
                VALUES (?, ?, 'open-meteo', ?)
            """, (church_id, elevation, now))
        
        fetched += len(results)
        if i % 20000 == 0 or i + BATCH_SIZE >= total:
            db.commit()
        
        sys.stdout.write(progress_bar(fetched, total, "  US Churches", start_time=t0))
        sys.stdout.flush()
        time.sleep(DELAY)
    
    db.commit()
    print(f"\n  Done: {fetched:,} US church elevations\n")

# ── Verify ──
tract_done = db.execute("SELECT COUNT(*) FROM tract_elevation").fetchone()[0]
church_done = db.execute("SELECT COUNT(*) FROM church_elevation").fetchone()[0]
print(f"=== VERIFICATION ===")
print(f"  Tract elevations: {tract_done:,}")
print(f"  Church elevations: {church_done:,}")

db.close()
print("\nPipeline complete. Ready for Step 3 (compute diffs).")

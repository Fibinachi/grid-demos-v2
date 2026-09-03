"""
Optimized elevation fetcher: sorts coordinates by COG tile to minimize tile opens.
Copernicus DEM 30m on AWS — global, free, no API key, no rate limits.
"""
import sqlite3, time, sys, math, signal
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import rasterio
from rasterio.windows import Window
from datetime import datetime

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

COG_BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"

def tile_key(lat, lon):
    """Returns (ns, lat_abs, ew, lon_abs) tuple"""
    ns = 'N' if lat >= 0 else 'S'
    ew = 'E' if lon >= 0 else 'W'
    la = abs(int(math.floor(lat)))
    lo = abs(int(math.floor(lon)))
    return (ns, la, ew, lo)

def cog_url(tile):
    """tile = (ns, lat, ew, lon)"""
    ns, la, ew, lo = tile
    tile_name = f"Copernicus_DSM_COG_10_{ns}{la:02d}_00_{ew}{lo:03d}_00_DEM"
    return f"{COG_BASE}/{tile_name}/{tile_name}.tif"

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

# Create tables
db.executescript("""
    CREATE TABLE IF NOT EXISTS church_elevation (
        church_id INTEGER PRIMARY KEY,
        elevation_m REAL NOT NULL,
        source TEXT DEFAULT 'copernicus-dem-30m',
        fetched_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tract_elevation (
        tract_fips TEXT PRIMARY KEY,
        elevation_m REAL NOT NULL,
        source TEXT DEFAULT 'copernicus-dem-30m',
        fetched_at TEXT
    );
""")
db.commit()

now = datetime.now().isoformat()

# ── PHASE 1: Tract centroids ──
print("=== PHASE 1: Tract Centroid Elevations ===\n")

needed = db.execute("""
    SELECT t.tract_fips, t.intpt_lat, t.intpt_lon 
    FROM tract_centroids_us t
    LEFT JOIN tract_elevation te ON t.tract_fips = te.tract_fips
    WHERE te.tract_fips IS NULL
""").fetchall()

if needed:
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    total = len(needed_sorted)
    fetched = 0
    skipped = 0
    t0 = time.time()
    current_tile = None
    src = None
    tiles_opened = 0
    
    for tract_fips, lat, lon in needed_sorted:
        tk = tile_key(lat, lon)
        
        if tk != current_tile:
            if src:
                src.close()
            try:
                src = rasterio.open(cog_url(tk))
                current_tile = tk
                tiles_opened += 1
                if tiles_opened % 50 == 0:
                    sys.stdout.write(f"\r  Tiles: {tiles_opened} opened | {fetched:,} elevations | ETA ~{(total-fetched)/max(fetched/(time.time()-t0),0.001)/60:.0f}min")
                    sys.stdout.flush()
            except Exception:
                current_tile = tk
                src = None
                skipped += 1
                continue
        
        if src is None:
            skipped += 1
            continue
        
        try:
            r, c = src.index(lon, lat)
            if 0 <= r < src.height and 0 <= c < src.width:
                e = src.read(1, window=Window(c, r, 1, 1))
                v = float(e[0, 0])
                if v > -100:
                    db.execute("INSERT OR REPLACE INTO tract_elevation VALUES (?,?,'copernicus-dem-30m',?)",
                              (tract_fips, v, now))
                    fetched += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        except:
            skipped += 1
        
        if fetched % 5000 == 0:
            db.commit()
        
        # Removed per-row progress bar — using tile-level progress instead
    
    if src:
        src.close()
    db.commit()
    print(f"\n  Done: {fetched:,} fetched, {skipped:,} skipped, {tiles_opened} tiles")

# ── PHASE 2: US Churches ──
print("\n=== PHASE 2: US Church Elevations ===\n")

needed = db.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'US' 
    AND c.latitude IS NOT NULL 
    AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""").fetchall()

if needed:
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    total = len(needed_sorted)
    fetched = 0
    skipped = 0
    t0 = time.time()
    current_tile = None
    src = None
    tiles_opened = 0
    
    for church_id, lat, lon in needed_sorted:
        tk = tile_key(lat, lon)
        
        if tk != current_tile:
            if src:
                src.close()
            try:
                src = rasterio.open(cog_url(tk))
                current_tile = tk
                tiles_opened += 1
                if tiles_opened % 100 == 0:
                    elapsed = time.time() - t0
                    rate = fetched / elapsed if elapsed > 0 else 0.001
                    eta_min = (total - fetched) / rate / 60 if rate > 0 else 0
                    sys.stdout.write(f"\r  Tiles: {tiles_opened} | {fetched:,} elevations | {rate:.0f}/s | ETA {eta_min:.0f}min")
                    sys.stdout.flush()
            except Exception:
                current_tile = tk
                src = None
                skipped += 1
                continue
        
        if src is None:
            skipped += 1
            continue
        
        try:
            r, c = src.index(lon, lat)
            if 0 <= r < src.height and 0 <= c < src.width:
                e = src.read(1, window=Window(c, r, 1, 1))
                v = float(e[0, 0])
                if v > -100:
                    db.execute("INSERT OR REPLACE INTO church_elevation VALUES (?,?,'copernicus-dem-30m',?)",
                              (church_id, v, now))
                    fetched += 1
                else:
                    skipped += 1
            else:
                skipped += 1
        except:
            skipped += 1
        
        if fetched % 20000 == 0:
            db.commit()
    
    if src:
        src.close()
    db.commit()
    print(f"\n  Done: {fetched:,} fetched, {skipped:,} skipped, {tiles_opened} tiles")

# ── Verify ──
tract_done = db.execute("SELECT COUNT(*) FROM tract_elevation").fetchone()[0]
church_done = db.execute("SELECT COUNT(*) FROM church_elevation").fetchone()[0]
print(f"\n=== VERIFICATION ===")
print(f"  Tract elevations: {tract_done:,}")
print(f"  Church elevations: {church_done:,}")

db.close()
print("\nPipeline complete!")

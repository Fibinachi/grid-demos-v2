"""
Robust elevation fetcher with tile pre-check, timeout, and global support.
Countries: US (remaining tracts + churches), BD, PH
"""
import sqlite3, time, sys, math, requests
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import rasterio
from rasterio.windows import Window
from datetime import datetime

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

COG_BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"

# Tile cache: pre-validated tile existence
BAD_TILES = set()      # tiles that returned 404
GOOD_TILES = {}        # tiles that exist: {tile_key: rasterio src or True}

def tile_key(lat, lon):
    ns = 'N' if lat >= 0 else 'S'
    ew = 'E' if lon >= 0 else 'W'
    return (ns, abs(int(math.floor(lat))), ew, abs(int(math.floor(lon))))

def cog_url(tile):
    ns, la, ew, lo = tile
    name = f"Copernicus_DSM_COG_10_{ns}{la:02d}_00_{ew}{lo:03d}_00_DEM"
    return f"{COG_BASE}/{name}/{name}.tif"

def tile_exists(tile):
    """Check if a tile exists without opening it"""
    if tile in BAD_TILES:
        return False
    if tile in GOOD_TILES:
        return True
    try:
        resp = requests.head(cog_url(tile), timeout=5)
        if resp.status_code == 200:
            GOOD_TILES[tile] = True
            return True
        else:
            BAD_TILES.add(tile)
            return False
    except Exception:
        BAD_TILES.add(tile)
        return False

def get_elevation(lat, lon):
    """Get elevation, returns None if unavailable"""
    tk = tile_key(lat, lon)
    if not tile_exists(tk):
        return None
    
    src = GOOD_TILES.get(tk)
    if src is True:
        try:
            src = rasterio.open(cog_url(tk))
            GOOD_TILES[tk] = src
        except Exception:
            BAD_TILES.add(tk)
            return None
    
    try:
        r, c = src.index(lon, lat)
        if 0 <= r < src.height and 0 <= c < src.width:
            e = src.read(1, window=Window(c, r, 1, 1))
            v = float(e[0, 0])
            return v if v > -100 else None
    except Exception:
        pass
    return None

def process_batch(coords, table, id_col, now, label=""):
    """Process a sorted list of (id, lat, lon) tuples into a table"""
    total = len(coords)
    fetched = 0
    skipped = 0
    t0 = time.time()
    processed = 0
    
    for obj_id, lat, lon in coords:
        processed += 1
        elev = get_elevation(lat, lon)
        
        if elev is not None:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,'copernicus-dem-30m',?)",
                      (obj_id, elev, now))
            fetched += 1
        else:
            skipped += 1
        
        if processed % 2000 == 0:
            db.commit()
            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - processed) / rate / 60 if rate > 0 else 0
            sys.stdout.write(f"\r  {label}: {processed:,}/{total:,} | {rate:.0f}/s | {fetched:,} ok, {skipped:,} skip | tiles: {len(GOOD_TILES)} good, {len(BAD_TILES)} bad | ETA {eta:.0f}min")
            sys.stdout.flush()
    
    db.commit()
    elapsed = time.time() - t0
    print(f"\r  {label}: {processed:,}/{total:,} DONE | {fetched:,} ok, {skipped:,} skip | {elapsed/60:.1f}min")
    return fetched, skipped

# Tables
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

# ── US TRACTS (remaining) ──
print("=== US TRACT CENTROIDS (remaining) ===\n")
needed = db.execute("""
    SELECT t.tract_fips, t.intpt_lat, t.intpt_lon 
    FROM tract_centroids_us t
    LEFT JOIN tract_elevation te ON t.tract_fips = te.tract_fips
    WHERE te.tract_fips IS NULL
""").fetchall()

if needed:
    print(f"  {len(needed):,} tracts remaining, sorting...", end="", flush=True)
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    print(" done.")
    process_batch(needed_sorted, 'tract_elevation', 'tract_fips', now, "US Tracts")

# ── US CHURCHES (remaining) ──
print("\n=== US CHURCHES (remaining) ===\n")
needed = db.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'US' 
    AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""").fetchall()

if needed:
    print(f"  {len(needed):,} churches remaining, sorting...", end="", flush=True)
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    print(" done.")
    process_batch(needed_sorted, 'church_elevation', 'church_id', now, "US Churches")

# ── BANGLADESH ──
print("\n=== BANGLADESH CHURCHES ===\n")
needed = db.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'BD' 
    AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""").fetchall()

if needed:
    print(f"  {len(needed):,} BD churches, sorting...", end="", flush=True)
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    print(" done.")
    process_batch(needed_sorted, 'church_elevation', 'church_id', now, "BD Churches")

# ── PHILIPPINES ──
print("\n=== PHILIPPINES CHURCHES ===\n")
needed = db.execute("""
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'PH' 
    AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""").fetchall()

if needed:
    print(f"  {len(needed):,} PH churches, sorting...", end="", flush=True)
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    print(" done.")
    process_batch(needed_sorted, 'church_elevation', 'church_id', now, "PH Churches")

# ── Cleanup ──
for key, val in GOOD_TILES.items():
    if hasattr(val, 'close'):
        val.close()

# ── Verify ──
tract_el = db.execute("SELECT COUNT(*) FROM tract_elevation").fetchone()[0]
church_el = db.execute("SELECT COUNT(*) FROM church_elevation").fetchone()[0]
bd_el = db.execute("""
    SELECT COUNT(*) FROM church_elevation ce 
    JOIN churches c ON c.id = ce.church_id WHERE c.country='BD'
""").fetchone()[0]
ph_el = db.execute("""
    SELECT COUNT(*) FROM church_elevation ce 
    JOIN churches c ON c.id = ce.church_id WHERE c.country='PH'
""").fetchone()[0]
us_el = db.execute("""
    SELECT COUNT(*) FROM church_elevation ce 
    JOIN churches c ON c.id = ce.church_id WHERE c.country='US'
""").fetchone()[0]

print(f"\n=== VERIFICATION ===")
print(f"  US tract elevations: {tract_el:,}")
print(f"  US church elevations: {us_el:,}")
print(f"  BD church elevations: {bd_el:,}")
print(f"  PH church elevations: {ph_el:,}")
print(f"  Total church elevations: {church_el:,}")
print(f"  Tiles: {len(GOOD_TILES)} good, {len(BAD_TILES)} bad")

db.close()
print("\nPipeline complete!")

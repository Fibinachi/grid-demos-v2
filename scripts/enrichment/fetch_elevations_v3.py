"""
Fast elevation fetcher — opens COG tiles directly, caches aggressively.
No HEAD pre-check — just try to open and catch errors.
"""
import sqlite3, time, sys, math
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import rasterio
from rasterio.windows import Window
from datetime import datetime

db = sqlite3.connect('churches.db')
db.execute("PRAGMA journal_mode=WAL")

COG_BASE = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"

TILE_CACHE = {}     # tile_key -> rasterio src or None (tried and failed)
FAILED_TILES = set()

def tile_key(lat, lon):
    ns = 'N' if lat >= 0 else 'S'; ew = 'E' if lon >= 0 else 'W'
    return (ns, abs(int(math.floor(lat))), ew, abs(int(math.floor(lon))))

def cog_url(tile):
    ns, la, ew, lo = tile
    name = f"Copernicus_DSM_COG_10_{ns}{la:02d}_00_{ew}{lo:03d}_00_DEM"
    return f"{COG_BASE}/{name}/{name}.tif"

def get_elev(lat, lon):
    tk = tile_key(lat, lon)
    if tk in FAILED_TILES:
        return None
    
    src = TILE_CACHE.get(tk)
    if src is None and tk not in FAILED_TILES:
        try:
            if len(TILE_CACHE) == 0:
                print(f"  [get_elev] Opening first tile: {tk}", flush=True)
            src = rasterio.open(cog_url(tk))
            TILE_CACHE[tk] = src
            if len(TILE_CACHE) == 1:
                print(f"  [get_elev] First tile opened OK", flush=True)
        except Exception as e:
            if len(FAILED_TILES) == 0:
                print(f"  [get_elev] First tile FAILED: {e}", flush=True)
            FAILED_TILES.add(tk)
            return None
    
    if src is None:
        return None
    
    try:
        r, c = src.index(lon, lat)
        if 0 <= r < src.height and 0 <= c < src.width:
            e = src.read(1, window=Window(c, r, 1, 1))
            v = float(e[0, 0])
            return v if v > -100 else None
    except:
        pass
    return None

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

def run_phase(label, query, table, id_col):
    print(f"\n=== {label} ===\n")
    needed = db.execute(query).fetchall()
    if not needed:
        print("  Nothing to do.")
        return
    
    print(f"  {len(needed):,} items, sorting...", end="", flush=True)
    needed_sorted = sorted(needed, key=lambda r: tile_key(r[1], r[2]))
    print(" done.")
    print(f"  First tile: {tile_key(needed_sorted[0][1], needed_sorted[0][2])}, starting loop...", flush=True)
    
    total = len(needed_sorted)
    ok = 0
    skip = 0
    t0 = time.time()
    
    for i, (obj_id, lat, lon) in enumerate(needed_sorted):
        if i == 0:
            print(f"  Processing first item: {obj_id} ({lat:.4f}, {lon:.4f})", flush=True)
        elev = get_elev(lat, lon)
        if elev is not None:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES (?,?,'copernicus-dem-30m',?)",
                      (obj_id, elev, now))
            ok += 1
        else:
            skip += 1
        
        if (i + 1) % 5000 == 0 or (i + 1) == total:
            db.commit()
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (total - i - 1) / rate / 60 if rate > 0 else 0
            sys.stdout.write(f"\r  {i+1:,}/{total:,} | {rate:.0f}/s | ok={ok:,} skip={skip:,} | tiles:{len(TILE_CACHE)} | ETA {eta:.0f}min")
            sys.stdout.flush()
    
    db.commit()
    print()
    return ok, skip

# ── RUN ──
# US Tracts
run_phase("US TRACT CENTROIDS", """
    SELECT t.tract_fips, t.intpt_lat, t.intpt_lon 
    FROM tract_centroids_us t
    LEFT JOIN tract_elevation te ON t.tract_fips = te.tract_fips
    WHERE te.tract_fips IS NULL
""", 'tract_elevation', 'tract_fips')

# US Churches
run_phase("US CHURCHES", """
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'US' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""", 'church_elevation', 'church_id')

# Bangladesh
run_phase("BANGLADESH CHURCHES", """
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'BD' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""", 'church_elevation', 'church_id')

# Philippines
run_phase("PHILIPPINES CHURCHES", """
    SELECT c.id, c.latitude, c.longitude
    FROM churches c
    LEFT JOIN church_elevation ce ON c.id = ce.church_id
    WHERE c.country = 'PH' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND ce.church_id IS NULL
""", 'church_elevation', 'church_id')

# ── Cleanup ──
for src in TILE_CACHE.values():
    if hasattr(src, 'close'):
        src.close()

# ── Stats ──
us_el = db.execute("SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='US'").fetchone()[0]
bd_el = db.execute("SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='BD'").fetchone()[0]
ph_el = db.execute("SELECT COUNT(*) FROM church_elevation ce JOIN churches c ON c.id=ce.church_id WHERE c.country='PH'").fetchone()[0]
tract_el = db.execute("SELECT COUNT(*) FROM tract_elevation").fetchone()[0]

print(f"\n{'='*60}")
print(f"  US tracts: {tract_el:,} | US churches: {us_el:,}")
print(f"  BD churches: {bd_el:,} | PH churches: {ph_el:,}")
print(f"  Tiles opened: {len(TILE_CACHE)} | Failed: {len(FAILED_TILES)}")
print(f"{'='*60}")
db.close()

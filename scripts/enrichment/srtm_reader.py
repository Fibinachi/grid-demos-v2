"""
Fast local SRTM elevation reader.
Downloads .hgt tiles on demand from USGS, caches locally.
SRTM3 (90m): 1201×1201 grid per 1° tile, ~2.9MB each.
"""
import os, struct, math, requests, time
import sqlite3
from datetime import datetime

SRTM_CACHE = "E:/grid/data/srtm"
SRTM_BASE_URL = "https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF"

# For US coverage: N25-N49, W67-W125 = 24 lat × 58 lon = ~1,392 tiles
# Each tile ~3MB → ~4GB total. Feasible.

os.makedirs(SRTM_CACHE, exist_ok=True)

def get_tile_names(lat, lon):
    """Get SRTM3 tile filename for a coordinate"""
    # SRTM3: 1201x1201, N{lat}E{lon}.hgt format
    n = int(math.floor(lat))
    e = int(math.floor(lon))
    return f"N{n:02d}E{e:03d}.hgt" if e >= 0 else f"N{n:02d}W{abs(e):03d}.hgt"

def download_tile(tile_name):
    """Download SRTM tile if not cached"""
    path = os.path.join(SRTM_CACHE, tile_name)
    if os.path.exists(path):
        return path
    
    # Try multiple sources
    urls = [
        f"https://srtm.csi.cgiar.org/wp-content/uploads/files/srtm_5x5/TIFF/{tile_name}.zip",
        f"https://e4ftl01.cr.usgs.gov/MEASURES/SRTMGL3.003/2000.02.11/{tile_name}.zip",
    ]
    
    for url in urls:
        try:
            resp = requests.get(url, timeout=30, stream=True)
            if resp.status_code == 200:
                import zipfile, io as io_mod
                with zipfile.ZipFile(io_mod.BytesIO(resp.content)) as z:
                    hgt_name = tile_name  # might be inside zip
                    # Check zip contents
                    for name in z.namelist():
                        if name.endswith('.hgt'):
                            hgt_name = name
                            break
                    z.extract(hgt_name, SRTM_CACHE)
                    if hgt_name != tile_name:
                        os.rename(os.path.join(SRTM_CACHE, hgt_name), path)
                print(f"    Downloaded {tile_name}")
                return path
        except Exception:
            continue
    
    return None

def read_elevation(lat, lon, path):
    """Read elevation from SRTM3 .hgt file"""
    # SRTM3: 1201 samples × 1201 lines, 16-bit big-endian signed
    # Cell size: 1/1200 degrees
    SIZE = 1201
    
    if not os.path.exists(path):
        return None
    
    with open(path, 'rb') as f:
        # Calculate row/col in the file
        # File covers [n, n+1] lat and [e, e+1] lon
        n = int(math.floor(lat))
        e = int(math.floor(lon))
        
        row_f = (n + 1 - lat) * (SIZE - 1)  # rows go north to south
        col_f = (lon - e) * (SIZE - 1)       # cols go west to east
        
        row = int(round(row_f))
        col = int(round(col_f))
        
        if row < 0 or row >= SIZE or col < 0 or col >= SIZE:
            return None
        
        offset = (row * SIZE + col) * 2
        f.seek(offset)
        raw = f.read(2)
        
        if len(raw) < 2:
            return None
        
        elev = struct.unpack('>h', raw)[0]  # big-endian signed 16-bit
        if elev <= -32768:  # void value
            return None
        
        return float(elev)


# ── Test ──
if __name__ == '__main__':
    print("=== SRTM READER TEST ===")
    
    # Test: download and read US Capitol
    lat, lon = 38.8899, -77.0091
    tile = get_tile_names(lat, lon)
    print(f"  Tile: {tile}")
    
    path = download_tile(tile)
    if path:
        elev = read_elevation(lat, lon, path)
        print(f"  US Capitol elevation: {elev}m")
    else:
        print(f"  Could not download tile")
    
    # Test batch speed
    import random
    random.seed(42)
    
    # Pre-download a few US tiles for testing
    test_coords = [(40.7128, -74.0060), (34.0522, -118.2437), (41.8781, -87.6298),
                   (29.7604, -95.3698), (33.4484, -112.0740)]
    
    print("\n  Testing batch reads:")
    for lat, lon in test_coords:
        tile = get_tile_names(lat, lon)
        path = download_tile(tile)
        if path:
            elev = read_elevation(lat, lon, path)
            print(f"    ({lat:.4f}, {lon:.4f}): {elev}m [{tile}]")
    
    # Speed test
    print("\n  Speed test (1000 random US points):")
    test_coords = [(random.uniform(25, 49), random.uniform(-125, -67)) for _ in range(1000)]
    
    t0 = time.time()
    hits = 0
    for lat, lon in test_coords:
        tile = get_tile_names(lat, lon)
        path = os.path.join(SRTM_CACHE, tile)
        if os.path.exists(path):
            read_elevation(lat, lon, path)
            hits += 1
        else:
            # Skip tiles not downloaded yet
            pass
    t1 = time.time()
    print(f"  {hits}/1000 queries in {t1-t0:.2f}s ({(t1-t0)/hits*1000:.1f}ms each)")
    
    # Estimate for full US run
    print(f"\n  Estimated for 983K churches: {983000 * (t1-t0)/1000:.0f}s = {983000 * (t1-t0)/1000/60:.0f} min")
    print(f"  SRTM tiles needed for US: ~1,400 (N25-N49, W67-W125)")
    print(f"  Tile download: ~1,400 × 3MB = ~4.2GB")

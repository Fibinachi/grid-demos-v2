"""Fix the 4 failed TIGER layers from the initial ingestion run.
These had wrong GENZ filenames or timed out.
"""
import sqlite3, sys, time, urllib.request, zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Point

PROJECT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT / "data" / "tiger"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = PROJECT / "churches.db"

# Fixed URLs
FIXES = [
    # SLDU + ZCTA already done — skip
    ("UAC20", "Urban Areas", "2020",
     "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_ua20_500k.zip",
     "cb_2020_us_ua20_500k.zip", "GEOID20"),
    ("PUMA20", "Public Use Microdata Areas", "2020",
     "https://www2.census.gov/geo/tiger/GENZ2020/shp/cb_2020_us_puma20_500k.zip",
     "cb_2020_us_puma20_500k.zip", "GEOID20"),
]

BATCH_COMMIT = 2000

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = time.time() - start
    rate = (i + 1) / elapsed if elapsed > 0 else 0
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    bar_len = 30
    filled = int(bar_len * (i + 1) / total)
    bar = chr(0x2588) * filled + chr(0x2591) * (bar_len - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) "
          f"rate={rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

def download(url, fname):
    path = DATA_DIR / fname
    if path.exists():
        return path
    print(f"    Downloading {fname} ...", end="", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                path.write_bytes(resp.read())
            print(f" {path.stat().st_size/1e6:.1f}MB")
            return path
        except Exception as e:
            if attempt == 2: raise
            print(f" retry...", end="", flush=True)
            time.sleep(10)

def main():
    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")

    # Get US churches with GPS
    cur = db.execute("SELECT id, latitude, longitude FROM churches WHERE country='US' AND latitude IS NOT NULL")
    church_points = cur.fetchall()
    church_count = len(church_points)
    print(f"  US churches with GPS: {church_count:,}")

    for layer_code, desc, cycle, url, fname, id_col in FIXES:
        print(f"\n  [{layer_code}] {desc}")

        # Check if already done
        cur = db.execute(
            "SELECT COUNT(*) FROM church_districts WHERE cycle_year=? AND layer_code=?",
            (cycle, layer_code))
        already = cur.fetchone()[0]
        if already > 0:
            print(f"    Already done: {already:,} rows. Skipping.")
            continue

        # Download and load
        zip_path = download(url, fname)
        extract_dir = DATA_DIR / f"{layer_code}_{cycle}"
        if not (extract_dir / zip_path.stem.replace(".zip", ".shp")).exists():
            extract_dir.mkdir(exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
        shp = list(extract_dir.glob("*.shp"))[0]

        gdf = gpd.read_file(shp, engine="pyogrio")
        print(f"    {len(gdf):,} polygons, id_col={id_col}")

        sindex = gdf.sindex
        start = time.time()
        batch = []
        assigned = 0

        for i, (ch_id, lat, lon) in enumerate(church_points):
            try:
                lat_f, lon_f = float(lat), float(lon)
            except (ValueError, TypeError):
                continue
            if lat_f is None or lon_f is None:
                continue

            point = Point(lon_f, lat_f)
            possible = list(sindex.intersection(point.bounds))
            match = None
            for idx in possible:
                if gdf.iloc[idx].geometry.contains(point):
                    match = gdf.iloc[idx]
                    break

            if match is not None:
                dist_code = str(match[id_col])
                name = match.get("NAMELSAD", match.get("NAME20", match.get("NAME", None)))
                geo = match.get("GEOID20", match.get("GEOID", str(match[id_col])))
                batch.append((ch_id, cycle, layer_code, dist_code, str(geo), name))
                assigned += 1

            if len(batch) >= BATCH_COMMIT:
                db.executemany("""
                    INSERT OR IGNORE INTO church_districts
                    (church_id, cycle_year, layer_code, district_code, geo_id, name)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, batch)
                db.commit()
                batch = []

            if (i + 1) % 25000 == 0:
                progress_bar(i, church_count, start)

        if batch:
            db.executemany("""
                INSERT OR IGNORE INTO church_districts
                (church_id, cycle_year, layer_code, district_code, geo_id, name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, batch)
            db.commit()

        elapsed = time.time() - start
        progress_bar(church_count - 1, church_count, start, f"done {elapsed:.0f}s")
        print(f"\n      {assigned:,} assigned ({elapsed:.0f}s)")

    db.close()
    print(f"\n  All 4 layers fixed.")

if __name__ == "__main__":
    main()

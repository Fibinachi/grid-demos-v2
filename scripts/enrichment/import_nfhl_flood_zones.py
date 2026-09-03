"""
NFHL Flood Zone Import + Spatial Join
=====================================
Downloads SFHA (high-risk) flood zone polygons from ArcGIS USA Flood Hazard
Reduced Set, builds spatial index, and classifies every US church by FEMA
flood zone. Zone X (safe/minimal risk) is inferred by exclusion.

Usage:
    python scripts/enrichment/import_nfhl_flood_zones.py --download  # resumable
    python scripts/enrichment/import_nfhl_flood_zones.py --join       # after download
    python scripts/enrichment/import_nfhl_flood_zones.py --all        # both (default)
    python scripts/enrichment/import_nfhl_flood_zones.py --summary    # stats only
"""

import sqlite3, json, time, urllib.request, struct, argparse
from pathlib import Path
from pyproj import Transformer

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"

_WEB_MERC_TO_WGS84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

SERVICE_URL = (
    "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
    "USA_Flood_Hazard_Reduced_Set_gdb/FeatureServer/0"
)

SFHA_WHERE = "SFHA_TF='T'"
SFHA_ZONES = {"A", "AE", "AH", "AO", "V", "VE", "D"}

ZONE_SEVERITY = {
    "V": 10, "VE": 10,
    "A": 8, "AE": 8, "AH": 8, "AO": 8,
    "D": 5, "A99": 8,
    "X": 0,
}

BATCH_SIZE = 1000
CHUNK_SIZE = 500


def progress_bar(i, total, start, label=""):
    if total == 0:
        return
    elapsed = max(time.time() - start, 0.001)
    rate = (i + 1) / elapsed
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    filled = int(30 * (i + 1) / total)
    bar = "\u2588" * filled + "\u2591" * (30 - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}",
          end="", flush=True)


def arcgis_to_wkb(geom):
    try:
        rings = geom.get("rings", [])
        if not rings:
            return None
        num_rings = len(rings)
        header = struct.pack("<bII", 1, 3, num_rings)
        ring_data = b""
        for ring in rings:
            num_points = len(ring)
            ring_data += struct.pack("<I", num_points)
            for pt in ring:
                lon, lat = _WEB_MERC_TO_WGS84.transform(pt[0], pt[1])
                ring_data += struct.pack("<dd", lon, lat)
        return header + ring_data
    except Exception:
        return None


def db_write_with_retry(db, sql, rows):
    """Write to SQLite with retry on database lock."""
    for attempt in range(10):
        try:
            db.executemany(sql, rows)
            db.commit()
            return
        except sqlite3.OperationalError:
            if attempt == 9:
                raise
            time.sleep((attempt + 1) * 1.5)


def download_polygons(db):
    """Download SFHA flood zone polygons from ArcGIS (resumable)."""
    print("=== DOWNLOADING NFHL SFHA FLOOD ZONE POLYGONS ===\n")

    # Get total SFHA count
    count_url = (
        f"{SERVICE_URL}/query?"
        f"where={urllib.request.quote(SFHA_WHERE)}"
        f"&returnCountOnly=true&f=json"
    )
    req = urllib.request.Request(count_url, headers={"User-Agent": "GRID/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = json.loads(r.read()).get("count", 0)
    print(f"SFHA polygons total: {total:,}")
    print(f"(Zone X = safe by exclusion — only downloading high-risk zones)\n")

    # Create table if not exists (resumable)
    db.execute("""
        CREATE TABLE IF NOT EXISTS nfhl_flood_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fld_zone TEXT NOT NULL,
            zone_subty TEXT,
            sfha_tf TEXT,
            dfirm_id TEXT,
            study_typ TEXT,
            geom_wkb BLOB NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_nfhl_zone ON nfhl_flood_zones(fld_zone)")
    db.commit()

    # Check where we left off
    existing = db.execute("SELECT COUNT(*) FROM nfhl_flood_zones").fetchone()[0]
    start_offset = existing
    if start_offset > 0:
        print(f"Resuming from offset {start_offset:,} ({existing:,} already saved)\n")

    out_fields = "FLD_ZONE,ZONE_SUBTY,SFHA_TF,DFIRM_ID,STUDY_TYP"
    inserted = existing
    failed = 0
    t0 = time.time()

    for offset in range(start_offset, total, BATCH_SIZE):
        url = (
            f"{SERVICE_URL}/query?"
            f"where={urllib.request.quote(SFHA_WHERE)}"
            f"&outFields={out_fields}"
            f"&returnGeometry=true&geometryPrecision=6"
            f"&resultOffset={offset}&resultRecordCount={BATCH_SIZE}&f=json"
        )

        # Retry on network failure
        data = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    data = json.loads(resp.read())
                break
            except Exception as e:
                if attempt == 4:
                    failed += 1
                    data = {"features": []}
                    print(f"\n  FAIL offset {offset}: {e}")
                else:
                    time.sleep((attempt + 1) * 10)

        rows = []
        for f in data.get("features", []):
            attrs = f.get("attributes", {})
            geom = f.get("geometry", {})
            zone = attrs.get("FLD_ZONE")
            if not zone or not geom:
                continue
            wkb = arcgis_to_wkb(geom)
            if wkb is None:
                continue
            rows.append((
                zone,
                attrs.get("ZONE_SUBTY"),
                attrs.get("SFHA_TF"),
                attrs.get("DFIRM_ID"),
                attrs.get("STUDY_TYP"),
                wkb,
            ))

        if rows:
            db_write_with_retry(db,
                "INSERT INTO nfhl_flood_zones (fld_zone, zone_subty, sfha_tf, "
                "dfirm_id, study_typ, geom_wkb) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            inserted += len(rows)

        progress_bar(min(offset + BATCH_SIZE, total), total, t0, f"{inserted:,}")

        # Anti-throttle: brief pause every 50 batches
        if (offset // BATCH_SIZE) % 50 == 0 and offset > 0:
            time.sleep(0.5)

    print(f"\n\nDownload complete: {inserted:,} SFHA polygons ({failed} failed batches)")
    for row in db.execute(
        "SELECT fld_zone, COUNT(*) FROM nfhl_flood_zones GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall():
        print(f"  Zone {row[0]:5s}: {row[1]:>10,}")
    return inserted


def spatial_join(db):
    """Point-in-polygon: classify every US church by FEMA flood zone."""
    print("\n=== SPATIAL JOIN: CHURCHES -> FLOOD ZONES ===\n")

    from shapely import wkb as shapely_wkb
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    print("Loading flood zone polygons...")
    rows = db.execute(
        "SELECT fld_zone, zone_subty, sfha_tf, geom_wkb FROM nfhl_flood_zones"
    ).fetchall()
    print(f"  {len(rows):,} polygons")

    print("Building STRtree spatial index...")
    t0 = time.time()
    geoms, zone_data = [], []
    for i, row in enumerate(rows):
        try:
            geom = shapely_wkb.loads(row[3])
            if geom.is_valid and not geom.is_empty:
                geoms.append(geom)
                zone_data.append((row[0], row[1], row[2]))
        except Exception:
            continue
        if (i + 1) % 500000 == 0:
            print(f"  {i+1:,} processed...")
    tree = STRtree(geoms)
    print(f"  {len(geoms):,} valid geometries in {time.time()-t0:.0f}s")

    print("\nLoading US church coordinates...")
    churches = db.execute("""
        SELECT c.id, c.latitude, c.longitude
        FROM churches c
        WHERE c.country='US' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    """).fetchall()
    print(f"  {len(churches):,} US churches with GPS")

    # Add columns
    cols = [c[1] for c in db.execute("PRAGMA table_info(church_enrichment)").fetchall()]
    for col in ["fema_flood_zone", "fema_flood_zone_subty", "fema_sfha", "fema_flood_updated"]:
        if col not in cols:
            db.execute(f"ALTER TABLE church_enrichment ADD COLUMN {col} TEXT")
    db.commit()

    db.execute("""
        INSERT OR IGNORE INTO church_enrichment (church_id)
        SELECT id FROM churches WHERE country='US' AND latitude IS NOT NULL
    """)
    db.commit()

    print("\nClassifying churches (not in SFHA = Zone X safe)...")
    t0 = time.time()
    in_sfha, zone_x = 0, 0

    for i in range(0, len(churches), CHUNK_SIZE):
        batch = churches[i:i + CHUNK_SIZE]
        updates = []

        for church_id, lat, lon in batch:
            point = Point(lon, lat)
            candidates = tree.query(point)

            best_z, best_s, best_f = None, None, None
            for idx in candidates:
                if geoms[idx].contains(point):
                    z, s, sfha = zone_data[idx]
                    if best_z is None or ZONE_SEVERITY.get(z, 0) > ZONE_SEVERITY.get(best_z, 0):
                        best_z, best_s, best_f = z, s, sfha

            if best_z:
                updates.append((best_z, best_s, best_f, church_id))
                in_sfha += 1
            else:
                updates.append(("X", None, "F", church_id))
                zone_x += 1

        for zone, subty, sfha, cid in updates:
            db.execute("""
                UPDATE church_enrichment
                SET fema_flood_zone = ?, fema_flood_zone_subty = ?,
                    fema_sfha = ?, fema_flood_updated = datetime('now')
                WHERE church_id = ?
            """, (zone, subty, sfha, cid))
        db.commit()

        progress_bar(i + len(batch), len(churches), t0,
                     f"{in_sfha:,} SFHA + {zone_x:,} Zone X")

    elapsed = time.time() - t0
    total = in_sfha + zone_x
    print(f"\n\nSpatial join: {total:,} churches in {elapsed/60:.1f}m ({total/elapsed:.0f} rec/s)")

    print("\n--- FEMA FLOOD ZONE DISTRIBUTION ---")
    for row in db.execute("""
        SELECT fema_flood_zone,
               CASE WHEN fema_flood_zone IN ('A','AE','AH','AO','V','VE','D')
                    THEN '[SFHA]' ELSE '' END,
               COUNT(*)
        FROM church_enrichment WHERE fema_flood_zone IS NOT NULL
        GROUP BY 1 ORDER BY 3 DESC
    """).fetchall():
        print(f"  Zone {row[0]:5s} {row[1]:7s}: {row[2]:>10,}")

    r = db.execute("SELECT COUNT(*) FROM church_enrichment WHERE fema_flood_zone='X'").fetchone()
    pct = r[0] / total * 100 if total else 0
    print(f"\n  HIGH GROUND (Zone X, minimal risk): {r[0]:,} ({pct:.1f}%)")
    print(f"  IN FLOOD ZONE (SFHA): {total - r[0]:,} ({100-pct:.1f}%)")


def show_summary(db):
    """Print flood zone stats (no download/join)."""
    r = db.execute("SELECT COUNT(*) FROM nfhl_flood_zones").fetchone()
    print(f"nfhl_flood_zones: {r[0]:,} polygons")

    r = db.execute(
        "SELECT COUNT(*) FROM church_enrichment WHERE fema_flood_zone IS NOT NULL"
    ).fetchone()
    if r[0] == 0:
        print("No churches classified yet. Run --join first.")
        return
    print(f"Churches classified: {r[0]:,}")
    for row in db.execute("""
        SELECT fema_flood_zone, COUNT(*)
        FROM church_enrichment WHERE fema_flood_zone IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC
    """).fetchall():
        sfha = " [SFHA]" if row[0] in SFHA_ZONES else ""
        print(f"  Zone {row[0]:5s}: {row[1]:>10,}{sfha}")


def main():
    p = argparse.ArgumentParser(description="NFHL flood zone import + spatial join")
    p.add_argument("--download", action="store_true")
    p.add_argument("--join", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--summary", action="store_true")
    args = p.parse_args()

    if not (args.download or args.join or args.all or args.summary):
        p.print_help()
        return

    db = sqlite3.connect(str(DB_PATH), timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")

    try:
        if args.summary:
            show_summary(db)
        else:
            if args.download or args.all:
                download_polygons(db)
            if args.join or args.all:
                spatial_join(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()

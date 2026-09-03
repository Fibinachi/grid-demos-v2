"""
SCRIPT: build_territory_tables.py
PURPOSE:
  1. Create ecclesiastical_territories table (load GoodLands GeoJSON → 2,838 rows)
  2. Create church_territories link table (church → territory with source/confidence)
  3. Migrate existing diocese data from church_enrichment into new tables
  4. Run global spatial join to tag ALL records (not just Catholic)
USAGE:  python scripts/geodata/build_territory_tables.py [--dry-run] [--batch-size N]
"""

import argparse, html, json, os, sqlite3, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from gw_db import connect, Provenance

# ─── paths ─────────────────────────────────────────────────────────────────
GEOJSON = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                       "data", "goodlands_diocesan_boundaries.geojson")
DB_PATH = "churches.db"

DIO_TYPE_LABELS = {
    "d": "Diocese", "a": "Archdiocese", "v": "Apostolic Vicariate",
    "p": "Territorial Prelature", "f": "Apostolic Prefecture",
    "e": "Eparchy", "t": "Territorial Abbey", "s": "Mission Sui Iuris",
    "i": "Ordinariate", "u": "Suburbicarian Diocese", "r": "Ordinariate",
    "x": "Personal Ordinariate", "8": "Diocese",
}

RITE_LABELS = {
    "la": "Latin", "sm": "Syro-Malabar", "er": "Eritrean",
    "et": "Ethiopian", "ia": "Italian-Albanian", "al": "Albanian",
    "sy": "Syrian", "ch": "Chaldean", "ma": "Maronite",
    "ru": "Russian", "ar": "Armenian", "co": "Coptic",
    "rt": "Ruthenian", "uk": "Ukrainian",
}


def format_full_name(name, diotype):
    if not name or (isinstance(name, float) and name != name):  # NaN check
        return ""
    name = html.unescape(str(name).strip())
    label = DIO_TYPE_LABELS.get(diotype, "")
    return f"{label} of {name}" if label else name


def create_tables(conn):
    """Create the new normalized tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ecclesiastical_territories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            full_name   TEXT,
            latin_name  TEXT,
            dio_type    TEXT,
            dio_type_label TEXT,
            metro_key   TEXT,
            country_key TEXT,
            rite_key    TEXT,
            rite_label  TEXT,
            population  INTEGER,
            vacant      INTEGER DEFAULT 0,
            region_key  TEXT,
            square_km   REAL,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS church_territories (
            church_id    INTEGER NOT NULL,
            territory_id INTEGER NOT NULL REFERENCES ecclesiastical_territories(id),
            source       TEXT NOT NULL,
            confidence   TEXT NOT NULL DEFAULT 'exact',
            notes        TEXT,
            created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (church_id, territory_id)
        );
        CREATE INDEX IF NOT EXISTS idx_ct_church ON church_territories(church_id);
        CREATE INDEX IF NOT EXISTS idx_ct_territory ON church_territories(territory_id);
    """)
    conn.commit()


def load_territories_from_geojson(conn, dry_run=False):
    """Load GoodLands GeoJSON into ecclesiastical_territories."""
    print(f"\nLoading territories from GoodLands GeoJSON ({GEOJSON})...")
    gdf = gpd.read_file(GEOJSON)
    print(f"  Loaded {len(gdf):,} features")

    inserted = 0
    for _, p in gdf.iterrows():
        name = html.unescape(str(p.get("Name", "") or "")).strip()
        if not name:
            continue
        full_name = format_full_name(name, p.get("DioType", ""))
        latin = html.unescape(str(p.get("LatinName", "") or "")).strip()
        diotype = p.get("DioType", "") or ""
        rite_key = p.get("RiteKey", "") or ""
        rite_label = RITE_LABELS.get(rite_key, "")
        vacant = 1 if p.get("Vacant") else 0
        pop = p.get("Population")
        if pop is None or pop == "None":
            pop = None
        else:
            try: pop = int(float(pop))
            except: pop = None
        sqkm = p.get("SquareKM")
        try:
            sqkm = float(sqkm)
        except:
            sqkm = None

        if not dry_run:
            conn.execute("""
                INSERT INTO ecclesiastical_territories
                    (name, full_name, latin_name, dio_type, dio_type_label,
                     metro_key, country_key, rite_key, rite_label,
                     population, vacant, region_key, square_km)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                name, full_name or name, latin, diotype,
                DIO_TYPE_LABELS.get(diotype, ""),
                p.get("MetroKey", "") or "",
                p.get("CountryKey", "") or "",
                rite_key, rite_label,
                pop, vacant,
                p.get("RegionKey", "") or "",
                sqkm
            ))
        inserted += 1

    if not dry_run:
        conn.commit()
    print(f"  Inserted {inserted} territory records")
    return inserted


def match_territory_by_name(conn, diocese_name):
    """Try to find a territory matching a diocese name from old enrichment data."""
    if not diocese_name:
        return None

    # Try exact full_name match
    row = conn.execute(
        "SELECT id FROM ecclesiastical_territories WHERE full_name = ?", (diocese_name,)
    ).fetchone()
    if row:
        return row[0]

    # Try name-only match (diocese_name might be just "Boston" not "Archdiocese of Boston")
    # Check if it contains " of " — e.g. "Diocese of Aachen" → "Aachen"
    if diocese_name.count(" of ") >= 1 and diocese_name.rindex(" of ") > 0:
        simple = diocese_name.split(" of ", 1)[-1].strip()
        row = conn.execute(
            "SELECT id FROM ecclesiastical_territories WHERE name = ? OR full_name LIKE ?",
            (simple, f"%{simple}%")
        ).fetchone()
        if row:
            return row[0]

    # Try partial match — diocese_name might be the full formatted name
    row = conn.execute(
        "SELECT id FROM ecclesiastical_territories WHERE ? LIKE '%' || name || '%' OR full_name LIKE ?",
        (diocese_name, f"%{diocese_name}%")
    ).fetchone()
    if row:
        return row[0]

    return None


def migrate_existing_diocese_data(conn, dry_run=False):
    """Migrate existing diocese/archdiocese/province from church_enrichment to church_territories."""
    print("\nMigrating existing enrichment diocese data...")

    rows = conn.execute("""
        SELECT church_id, diocese, archdiocese, province, rite, catholic_hierarchy_source
        FROM church_enrichment
        WHERE diocese IS NOT NULL AND diocese != ''
    """).fetchall()
    print(f"  {len(rows)} enrichment rows with diocese data")

    matched = 0
    unmatched = 0
    unmatched_names = set()

    for row in rows:
        cid, diocese, archdiocese, province, rite, source = row
        tid = match_territory_by_name(conn, diocese)

        if tid:
            if not dry_run:
                conn.execute("""
                    INSERT OR IGNORE INTO church_territories
                        (church_id, territory_id, source, confidence, notes)
                    VALUES (?, ?, ?, 'exact', ?)
                """, (cid, tid,
                      source or "goodlands_diocesan_boundaries_v2_2019",
                      f"archdiocese={archdiocese or ''} province={province or ''} rite={rite or ''}"))
            matched += 1
        else:
            unmatched += 1
            unmatched_names.add(diocese)

    if not dry_run:
        conn.commit()

    print(f"  Matched: {matched}")
    print(f"  Unmatched: {unmatched}")
    if unmatched_names:
        print(f"  Unmatched sample (up to 20): {sorted(unmatched_names)[:20]}")
    return matched, unmatched


def verify_migration(conn):
    """Verify the migration."""
    print("\n=== VERIFICATION ===")

    # Territory counts
    cnt = conn.execute("SELECT COUNT(*) FROM ecclesiastical_territories").fetchone()[0]
    print(f"Territories: {cnt}")
    cnt = conn.execute("SELECT COUNT(DISTINCT country_key) FROM ecclesiastical_territories WHERE country_key != ''").fetchone()[0]
    print(f"Countries represented: {cnt}")

    # Territory type breakdown
    print("\n=== Territory types ===")
    for r in conn.execute("SELECT dio_type_label, COUNT(*) FROM ecclesiastical_territories WHERE dio_type_label != '' GROUP BY dio_type_label ORDER BY COUNT(*) DESC").fetchall():
        print(f"  {r[0]:30s} {r[1]}")

    # Rite breakdown
    print("\n=== Rites ===")
    for r in conn.execute("SELECT rite_label, COUNT(*) FROM ecclesiastical_territories WHERE rite_label != '' GROUP BY rite_label ORDER BY COUNT(*) DESC").fetchall():
        print(f"  {r[0]:30s} {r[1]}")

    # Link counts
    ct = conn.execute("SELECT COUNT(*) FROM church_territories").fetchone()[0]
    unique_churches = conn.execute("SELECT COUNT(DISTINCT church_id) FROM church_territories").fetchone()[0]
    print(f"\nChurch-territory links: {ct} (unique churches: {unique_churches})")

    # Sample
    print("\n=== Sample links ===")
    for r in conn.execute("""
        SELECT ct.church_id, et.full_name, ct.source, ct.confidence,
               c.name, c.faith_tradition, c.country
        FROM church_territories ct
        JOIN ecclesiastical_territories et ON ct.territory_id = et.id
        JOIN churches c ON ct.church_id = c.id
        LIMIT 10
    """).fetchall():
        print(f'  church={r[0]:>10} {r[1]:45s} src={r[2]:20s} conf={r[3]:10s} faith={str(r[5]):15s} {r[6]}')


def spatial_tag_all(conn, diocese_gdf, batch_size=25000, dry_run=False):
    """Spatial join ALL records with coordinates against territory polygons."""
    print("\n=== SPATIAL TAGGING ALL RECORDS ===")

    total = conn.execute("""
        SELECT COUNT(DISTINCT id) FROM churches
        WHERE id IS NOT NULL
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """).fetchone()[0]
    print(f"Total records with coordinates: {total:,}")

    # Territory lookup
    ter_rows = conn.execute("SELECT id, name, full_name FROM ecclesiastical_territories").fetchall()
    name_to_tid = {}
    for tid, name, fname in ter_rows:
        if fname:
            name_to_tid[fname] = tid
        if name:
            name_to_tid[name] = tid

    # Build name→tid mapping from GeoDataFrame
    territory_name_map = {}
    for _, feat in diocese_gdf.iterrows():
        fname = format_full_name(feat.get("Name", ""), feat.get("DioType", ""))
        if fname and fname in name_to_tid:
            territory_name_map[fname] = name_to_tid[fname]

    # Add territory_id to the polygon GDF
    diocese_gdf["full_name"] = diocese_gdf.apply(
        lambda r: format_full_name(r.get("Name", ""), r.get("DioType", "")), axis=1
    )
    diocese_gdf["territory_id"] = diocese_gdf["full_name"].map(territory_name_map)
    valid_gdf = diocese_gdf[diocese_gdf["territory_id"].notna()].copy()
    print(f"  Valid polygons with territory_id: {len(valid_gdf)}")

    offset = 0
    total_tagged = 0
    start_time = time.time()

    while offset < total:
        batch_start = time.time()

        # Load ID + coords directly in the batch — use DISTINCT for unique entities
        rows = conn.execute("""
            SELECT DISTINCT id, latitude, longitude FROM churches
            WHERE id IS NOT NULL
              AND latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY id LIMIT ? OFFSET ?
        """, (batch_size, offset)).fetchall()
        if not rows:
            break

        df = pd.DataFrame(rows, columns=["id", "latitude", "longitude"])
        df["geometry"] = df.apply(lambda r: Point(r["longitude"], r["latitude"]), axis=1)
        points_gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

        # Spatial join
        joined = gpd.sjoin(
            points_gdf,
            valid_gdf[["territory_id", "full_name", "geometry"]],
            predicate="within", how="left"
        )

        tagged = joined[joined["territory_id"].notna()]
        tagged = tagged[~tagged.index.duplicated(keep="first")]

        # Write — INSERT OR IGNORE handles any already-linked records
        if not dry_run and len(tagged) > 0:
            records = [(r["id"], int(r["territory_id"]),
                        "goodlands_diocesan_boundaries_v2_2019", "exact")
                       for _, r in tagged.iterrows()]
            conn.executemany("""
                INSERT OR IGNORE INTO church_territories
                    (church_id, territory_id, source, confidence)
                VALUES (?, ?, ?, ?)
            """, records)
            conn.commit()

        total_tagged += len(tagged)

        batch_elapsed = time.time() - batch_start
        rate = len(rows) / batch_elapsed if batch_elapsed > 0 else 0
        print(f"  Batch {offset:,}-{offset + len(rows):,}: "
              f"tagged={len(tagged):,} outside={len(rows) - len(tagged):,}"
              f" ({rate:.0f} rec/s)")

        offset += len(rows)

    elapsed = time.time() - start_time
    print(f"\n=== SPATIAL TAG SUMMARY ===")
    print(f"  Total processed: {offset:,}")
    print(f"  Newly tagged:    {total_tagged:,}")
    print(f"  Time:            {elapsed:.0f}s ({offset/elapsed:.0f} rec/s)")
    return total_tagged


def main():
    parser = argparse.ArgumentParser(description="Build territory tables and run global spatial join")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database")
    parser.add_argument("--batch-size", type=int, default=25000, help="Batch size")
    parser.add_argument("--skip-spatial", action="store_true", help="Skip the global spatial join")
    args = parser.parse_args()

    print("=" * 60)
    print("ECCLESIASTICAL TERRITORY TABLE BUILDER")
    print(f"  Dry run: {args.dry_run}")
    print("=" * 60)

    conn = connect(DB_PATH)

    # Step 1: Create tables
    print("\n--- Step 1: Creating tables ---")
    create_tables(conn)
    print("  ecclesiastical_territories + church_territories created")

    # Step 2: Load territories from GeoJSON (skip if already loaded)
    existing_territories = conn.execute("SELECT COUNT(*) FROM ecclesiastical_territories").fetchone()[0]
    if existing_territories > 0:
        print(f"\n--- Step 2: Skipping — {existing_territories} territories already loaded ---")
    else:
        print("\n--- Step 2: Loading territories from GoodLands ---")
        if not args.dry_run:
            conn.execute("DELETE FROM ecclesiastical_territories")
            conn.commit()
        load_territories_from_geojson(conn, args.dry_run)

    # Step 3: Migrate existing enrichment data (skip if already done)
    existing_links = conn.execute("SELECT COUNT(*) FROM church_territories").fetchone()[0]
    if existing_links > 0:
        print(f"\n--- Step 3: Skipping — {existing_links} church-territory links already exist ---")
    else:
        print("\n--- Step 3: Migrating existing enrichment diocese data ---")
        migrate_existing_diocese_data(conn, args.dry_run)

    # Step 4: Verify
    if not args.dry_run:
        verify_migration(conn)

    # Step 5: Global spatial join
    if not args.skip_spatial:
        diocese_gdf = gpd.read_file(GEOJSON)
        spatial_tag_all(conn, diocese_gdf, args.batch_size, args.dry_run)
        if not args.dry_run:
            verify_migration(conn)

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

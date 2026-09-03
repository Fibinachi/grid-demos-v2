"""
SCRIPT: spatial_assign_us_county.py
PURPOSE:
  Assign county_fips_5 to all US churches with GPS coordinates but no
  county FIPS via point-in-polygon spatial join with Census county boundaries.
  
  Then re-run church_rucc to cover the newly assigned counties.

  Data flow:
    1. Load Census 2024 county boundaries (EPSG:4269)
    2. Extract US churches with lat/lon but no county_fips_5
    3. Spatial join (point-in-polygon)
    4. Write county_fips_5 (+ county name) back to churches table
    5. Re-run populate_church_rucc.py

  Source: Census Bureau TIGER/Line 2024 (cartographic 1:500K)
    data/census_tiger/cb_2024_us_county_500k.shp

USAGE:
    python scripts/geodata/spatial_assign_us_county.py
    python scripts/geodata/spatial_assign_us_county.py --dry-run
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import geopandas as gpd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect, Provenance
import pandas as pd
from gw_db import connect

DB_PATH = "churches.db"
COUNTY_SHP = "data/census_tiger/cb_2024_us_county_500k.shp"


def main():
    parser = argparse.ArgumentParser(
        description="Assign US county FIPS via spatial join"
    )
    parser.add_argument("--dry-run", action="store_true", help="Counts only, no writes")
    parser.add_argument("--batch-size", type=int, default=100000,
                        help="Update batch size (default: 100K)")
    args = parser.parse_args()

    db = connect(DB_PATH)
    start = time.time()

    # ─── Step 1: Load county boundaries ──────────────────────────────────
    print("=== Spatial county assignment for US churches ===\n")
    print(f"Loading county boundaries from {COUNTY_SHP}...")
    counties = gpd.read_file(COUNTY_SHP)
    # Keep only what we need + ensure CRS is lat/lon
    if counties.crs is None or counties.crs.to_string() != "EPSG:4269":
        counties = counties.to_crs("EPSG:4269")
    print(f"  {len(counties):,} county polygons loaded")
    print(f"  CRS: {counties.crs}")

    # ─── Step 2: Extract churches needing county FIPS ────────────────────
    print("\nQuerying US churches with GPS coordinates...")
    c = db.cursor()
    c.execute("""
        SELECT rowid, latitude, longitude, id, county, city, state
        FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL AND longitude IS NOT NULL
    """)
    rows = c.fetchall()

    if not rows:
        print("  No churches need county FIPS assignment! ✅")
        return

    print(f"  {len(rows):,} churches to process")

    # Show state breakdown
    state_counts = {}
    for r in rows:
        st = r[6] or "??"
        state_counts[st] = state_counts.get(st, 0) + 1
    top_states = sorted(state_counts.items(), key=lambda x: -x[1])[:10]
    print(f"  Top states: {', '.join(f'{s}={n:,}' for s, n in top_states)}")

    if args.dry_run:
        print("\nDry run complete. No changes made.")
        return

    # ─── Step 3: Build church points GeoDataFrame ────────────────────────
    print("\nBuilding point geometry...")
    df_churches = pd.DataFrame(rows, columns=[
        "rowid", "latitude", "longitude", "id", "county", "city", "state"
    ])
    # Filter invalid coords
    before = len(df_churches)
    df_churches = df_churches[
        (df_churches["latitude"].between(-90, 90)) &
        (df_churches["longitude"].between(-180, 180))
    ]
    skipped = before - len(df_churches)
    if skipped:
        print(f"  Skipped {skipped:,} rows with invalid coords")

    points = gpd.GeoDataFrame(
        df_churches,
        geometry=gpd.points_from_xy(df_churches["longitude"], df_churches["latitude"]),
        crs="EPSG:4326",
    )
    # Transform to match county CRS
    points = points.to_crs(counties.crs)
    print(f"  {len(points):,} points ready for spatial join")

    # ─── Step 4: Spatial join ────────────────────────────────────────────
    print("\nPerforming spatial join (point-in-polygon)...")
    t0 = time.time()
    # Use predicate='within' for points inside polygons
    joined = gpd.sjoin(
        points, counties[["GEOID", "NAME", "STATEFP", "geometry"]],
        predicate="within",
        how="left",
    )
    elapsed = time.time() - t0
    print(f"  Spatial join completed in {elapsed:.1f}s")

    matched = joined["GEOID"].notna().sum()
    unmatched = joined["GEOID"].isna().sum()
    print(f"  Matched to county: {matched:,}")
    print(f"  No match (offshore/territory): {unmatched:,}")

    # ─── Step 5: Write county_fips_5 back to churches table ──────────────
    print("\nWriting county FIPS back to churches table...")

    # Build update list: (rowid, fips, county_name)
    matched_df = joined[joined["GEOID"].notna()].copy()
    matched_df["county_fips_5"] = matched_df["GEOID"].astype(str).str.zfill(5)
    matched_df["county_name"] = matched_df["NAME"]

    updates = list(matched_df[["rowid", "county_fips_5", "county_name"]].itertuples(
        index=False, name=None
    ))

    print(f"  {len(updates):,} rows to update")
    updated_total = 0
    batch_size = args.batch_size

    # Use PRAGMA settings for speed
    db.execute("PRAGMA synchronous = OFF")
    db.execute("PRAGMA cache_size = -8000000")  # 8 GB cache
    db.execute("PRAGMA temp_store = MEMORY")

    # Create temp table + bulk INSERT with executemany
    db.execute("DROP TABLE IF EXISTS _county_updates")
    db.execute("""
        CREATE TEMP TABLE _county_updates (
            rowid INTEGER PRIMARY KEY,
            county_fips_5 TEXT,
            county_name TEXT
        )
    """)

    for i in range(0, len(updates), batch_size):
        batch = updates[i : i + batch_size]
        t0 = time.time()

        db.executemany(
            "INSERT INTO _county_updates (rowid, county_fips_5, county_name) VALUES (?, ?, ?)",
            batch,
        )
        db.commit()

        elapsed = time.time() - t0
        updated_total += len(batch)
        pct = updated_total / len(updates) * 100
        rate = len(batch) / elapsed if elapsed > 0 else 0
        print(f"  Inserted temp: {updated_total:,}/{len(updates):,} ({pct:.0f}%)  "
              f"{rate:,.0f} rows/s")

    # Single UPDATE FROM — much faster than per-row CASE
    print("\nRunning bulk UPDATE FROM...")
    t0 = time.time()
    db.execute("""
        UPDATE churches
        SET county_fips_5 = u.county_fips_5,
            county = u.county_name
        FROM _county_updates u
        WHERE churches.rowid = u.rowid
    """)
    db.commit()
    update_elapsed = time.time() - t0
    print(f"  Bulk update completed in {update_elapsed:.1f}s")

    db.execute("DROP TABLE IF EXISTS _county_updates")
    db.execute("PRAGMA synchronous = FULL")

    # ─── Step 6: Summary ─────────────────────────────────────────────────
    print("\n=== Summary ===")
    total_time = time.time() - start
    print(f"  Churches updated: {updated_total:,}")
    print(f"  No match (offshore): {unmatched:,}")
    print(f"  Total time: {total_time:.0f}s")

    # Quick verification
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL
          AND county_fips_5 IS NOT NULL AND county_fips_5 != ''
    """)
    with_fips_now = c.fetchone()[0]
    print(f"\n  US churches WITH county FIPS: {with_fips_now:,}")

    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE country = 'US'
          AND latitude IS NOT NULL
          AND (county_fips_5 IS NULL OR county_fips_5 = '')
    """)
    still_missing = c.fetchone()[0]
    print(f"  Still missing county FIPS: {still_missing:,}")

    # ─── Provenance ──────────────────────────────────────────────────────
    with Provenance(
        conn=db,
        source="census_tiger_2024",
        script_name="spatial_assign_us_county.py",
        action="enriched",
        fields="county_fips_5, county",
        params=f"Spatial join (point-in-polygon) using Census TIGER/Line 2024 counties. "
               f"{updated_total:,} matched, {unmatched:,} unmatched (offshore). "
               f"Shapefile: data/census_tiger/cb_2024_us_county_500k.shp.",
    ) as p:
        p.churches_updated = updated_total

    print("\nDone. Run populate_church_rucc.py next to pick up new FIPS.")


if __name__ == "__main__":
    main()

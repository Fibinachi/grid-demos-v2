#!/usr/bin/env python3
"""
Spatial tagging script: assign Catholic church records to their diocese
using the GoodLands Global Diocesan Boundaries v2.0 (2019) polygon dataset.

Pipeline:
  1. Load GeoJSON diocese boundaries into GeoDataFrame
  2. Load Catholic church records (faith_tradition='Catholic') with coordinates
  3. Spatial join (point-in-polygon) using geopandas sjoin
  4. Write diocese, province, etc. into church_enrichment
  5. Log all operations in provenance_log

Usage:
  python scripts/geodata/spatial_tag_dioceses.py [--dry-run] [--batch-size N]

License note: The boundary data is CC-BY-ND-4.0. Point-in-polygon tagging
is a separate derived use — we are not modifying the polygon data itself,
so this is acceptable.
"""

import argparse
import html
import json
import os
import sys
import time
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import geopandas as gpd
import pandas as pd
from shapely import wkt
from shapely.geometry import Point

from gw_db import connect, Provenance, log_change

# ─── config ────────────────────────────────────────────────────────────────
GEOJSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "goodlands_diocesan_boundaries.geojson"
)
DB_PATH = "churches.db"

DIO_TYPE_LABELS = {
    "d": "Diocese",
    "a": "Archdiocese",
    "v": "Apostolic Vicariate",
    "p": "Territorial Prelature",
    "f": "Apostolic Prefecture",
    "e": "Eparchy",
    "t": "Territorial Abbey",
    "s": "Mission Sui Iuris",
    "i": "Ordinariate",
    "u": "Suburbicarian Diocese",
    "r": "Ordinariate",
    "x": "Personal Ordinariate",
    "8": "Diocese",  # data issue, treat as diocese
}

SCRIPT_NAME = "scripts/geodata/spatial_tag_dioceses.py"
SOURCE_NAME = "goodlands_diocesan_boundaries_v2_2019"


def format_diocese_name(name: str, diotype: str) -> str:
    """Format a proper diocese name like 'Diocese of Aachen' or 'Archdiocese of Boston'."""
    if not name:
        return ""
    name = html.unescape(name.strip())
    label = DIO_TYPE_LABELS.get(diotype, "")
    if not label:
        return name
    # Special: for some names like "Porto-Santa Rufina" don't add "of"
    # but for most names use "of"
    label = DIO_TYPE_LABELS.get(diotype, "")
    if not label:
        return name
    return f"{label} of {name}"


def load_boundaries():
    """Load the GeoJSON diocese boundaries into a GeoDataFrame."""
    print(f"Loading boundaries from {GEOJSON_PATH}...")
    gdf = gpd.read_file(GEOJSON_PATH)
    print(f"  Loaded {len(gdf):,} polygon features")

    # Clean names
    gdf["Name"] = gdf["Name"].apply(lambda x: html.unescape(str(x).strip()) if x else "")
    gdf["LatinName"] = gdf["LatinName"].apply(lambda x: html.unescape(str(x).strip()) if x else "")

    # Build formatted diocese name
    gdf["diocese_name"] = gdf.apply(
        lambda r: format_diocese_name(r.get("Name", ""), r.get("DioType", "")),
        axis=1
    )

    # Ensure WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting from {gdf.crs.to_epsg()} to 4326...")
        gdf = gdf.to_crs("EPSG:4326")

    print(f"  CRS: {gdf.crs}")
    print(f"  Bounds: {gdf.total_bounds}")
    print(f"  Diocese names sample: {gdf['diocese_name'].head(5).tolist()}")

    # Count by DioType
    print(f"\n  === Diocese counts by type ===")
    for dt, cnt in gdf["DioType"].value_counts().sort_index().items():
        label = DIO_TYPE_LABELS.get(dt, dt)
        print(f"    [{dt}] {label}: {cnt}")

    return gdf


def load_churches(conn, batch_size=25000):
    """Load Catholic church records from the database in batches."""
    print(f"\nLoading Catholic church records (batch_size={batch_size})...")

    # First get total count of DISTINCT church_ids
    c = conn.cursor()
    c.execute("SELECT COUNT(DISTINCT id) FROM churches WHERE faith_tradition='Catholic' AND latitude IS NOT NULL AND longitude IS NOT NULL")
    total = c.fetchone()[0]
    print(f"  Total unique Catholic church_ids with coordinates: {total:,}")

    # Also report total rows (with duplicates) for comparison
    c.execute("SELECT COUNT(*) FROM churches WHERE faith_tradition='Catholic' AND latitude IS NOT NULL AND longitude IS NOT NULL")
    total_rows = c.fetchone()[0]
    print(f"  Total Catholic rows (including duplicate IDs): {total_rows:,}")

    offset = 0
    while offset < total:
        c.execute("""
            SELECT ch.id,
                   MIN(ch.latitude) as latitude,
                   MIN(ch.longitude) as longitude,
                   MIN(ch.country) as country,
                   MIN(ce.diocese) as existing_diocese
            FROM churches ch
            LEFT JOIN church_enrichment ce ON ch.id = ce.church_id
            WHERE ch.faith_tradition='Catholic'
              AND ch.latitude IS NOT NULL AND ch.longitude IS NOT NULL
            GROUP BY ch.id
            ORDER BY ch.id
            LIMIT ? OFFSET ?
        """, (batch_size, offset))

        rows = c.fetchall()
        if not rows:
            break

        df = pd.DataFrame(rows, columns=["id", "latitude", "longitude", "country", "existing_diocese"])
        df["geometry"] = df.apply(lambda r: Point(r["longitude"], r["latitude"]), axis=1)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

        yield gdf, offset, total
        offset += len(rows)


def main():
    parser = argparse.ArgumentParser(description="Spatially tag Catholic churches with diocese boundaries")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to database, only report")
    parser.add_argument("--batch-size", type=int, default=25000, help="Church batch size (default: 25000)")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip records that already have a diocese (default: True)")
    args = parser.parse_args()

    print("=" * 60)
    print("GOODLANDS DIOCESAN BOUNDARIES — SPATIAL TAGGING")
    print(f"  Dry run: {args.dry_run}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Skip existing: {args.skip_existing}")
    print("=" * 60)

    # Load boundaries
    diocese_gdf = load_boundaries()

    # Build spatial index
    print("\nBuilding spatial index...")
    sindex = diocese_gdf.sindex
    print("  Done")

    conn = connect(DB_PATH)

    total_processed = 0
    total_tagged = 0
    total_already_had = 0
    total_outside = 0
    total_multiple = 0

    # Track country-level stats
    country_new = defaultdict(int)
    country_outside = defaultdict(int)

    # Check what records already have diocese to skip
    if args.skip_existing:
        c = conn.cursor()
        c.execute("""
            SELECT ch.id FROM churches ch
            JOIN church_enrichment ce ON ch.id = ce.church_id
            WHERE ch.faith_tradition='Catholic'
              AND ce.diocese IS NOT NULL AND ce.diocese != ''
        """)
        existing_ids = set(row[0] for row in c.fetchall())
        print(f"\nRecords already with diocese (will skip): {len(existing_ids):,}")
    else:
        existing_ids = set()

    # Get total count for provenance/display (use DISTINCT IDs)
    c2 = conn.cursor()
    c2.execute("SELECT COUNT(DISTINCT id) FROM churches WHERE faith_tradition='Catholic' AND latitude IS NOT NULL AND longitude IS NOT NULL")
    total_catholic_with_coords = c2.fetchone()[0]

    # Set up provenance tracking
    provenance_rec = None
    if not args.dry_run:
        provenance_rec = Provenance(conn, SCRIPT_NAME, source=SOURCE_NAME,
                                    fields="diocese,diocese_detail,province_detail",
                                    records_attempted=total_catholic_with_coords)
        provenance_rec.__enter__()

    start_time = time.time()

    for church_gdf, offset, total in load_churches(conn, args.batch_size):
        batch_start = time.time()

        # Separate into new vs existing
        if existing_ids:
            new_mask = ~church_gdf["id"].isin(existing_ids)
            new_gdf = church_gdf[new_mask].copy()
            skip_gdf = church_gdf[~new_mask].copy()
            total_already_had += len(skip_gdf)
        else:
            new_gdf = church_gdf.copy()

        if len(new_gdf) == 0:
            total_processed += len(church_gdf)
            continue

        # Spatial join: find which diocese polygon each point falls within
        joined = gpd.sjoin(
            new_gdf,
            diocese_gdf[["diocese_name", "Name", "DioType", "CountryKey", "RiteKey", "MetroKey",
                         "Population", "geometry"]],
            predicate="within",
            how="left"
        )

        # Separate tagged from not-tagged
        tagged = joined[joined["diocese_name"].notna()].copy()
        outside = joined[joined["diocese_name"].isna()].copy()

        # Handle potential duplicates (point within multiple diocese polygons)
        if len(tagged) > 0:
            dup_mask = tagged.index.duplicated(keep=False)
            if dup_mask.any():
                # For duplicates, keep only the first match (index_right is first match)
                # Log the extra ones as diocese_detail candidates
                first_only = tagged[~tagged.index.duplicated(keep="first")]
                # Save which ones had multiple matches
                multi_indices = set(tagged[dup_mask].index)

                # Store the secondary diocese names for multi-match churches
                # This will be handled below

                tagged = first_only

            total_multiple += len(tagged[tagged.index.duplicated(keep=False)])

        batch_tagged = len(tagged)
        batch_outside = len(outside)
        total_tagged += batch_tagged
        total_outside += batch_outside

        # Track country stats
        for _, row in tagged.iterrows():
            country_new[row.get("country", "??")] += 1
        for _, row in outside.iterrows():
            country_outside[row.get("country", "??")] += 1

        # Write to database (unless dry run)
        if not args.dry_run and batch_tagged > 0:
            c = conn.cursor()
            updates = []
            for _, row in tagged.iterrows():
                updates.append((
                    row["diocese_name"],
                    row.get("Name", "") or "",
                    row.get("DioType", "") or "",
                    row.get("MetroKey", "") or "",
                    row.get("CountryKey", "") or "",
                    row["id"],
                ))

            # Batch UPSERT via executemany
            c.executemany("""
                INSERT INTO church_enrichment (church_id, diocese, diocese_detail, province_detail)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(church_id) DO UPDATE SET
                    diocese = COALESCE(NULLIF(excluded.diocese, ''), church_enrichment.diocese),
                    diocese_detail = excluded.diocese_detail,
                    province_detail = excluded.province_detail
            """, [
                (
                    row_id,
                    diocese_name,
                    f"DioType: {diotype} | Name: {name}" if name else "",
                    f"MetroKey: {metro}" if metro else "",
                )
                for diocese_name, name, diotype, metro, ckey, row_id in updates
            ])
            conn.commit()

        # Track for provenance logging
        if provenance_rec is not None:
            provenance_rec.records_matched += batch_tagged
            provenance_rec.churches_updated += batch_tagged

        total_processed += len(church_gdf)
        elapsed = time.time() - batch_start
        rate = len(church_gdf) / elapsed if elapsed > 0 else 0
        print(f"  Batch {offset:,}-{offset + len(church_gdf):,}: "
              f"tagged={batch_tagged:,} outside={batch_outside:,} "
              f"skip={len(skip_gdf) if existing_ids else 0:,} "
              f"({rate:.0f} rec/s)")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"SUMMARY (dry_run={args.dry_run})")
    print(f"{'=' * 60}")
    print(f"  Total processed: {total_processed:,}")
    print(f"  Newly tagged:    {total_tagged:,}")
    print(f"  Already had:     {total_already_had:,}")
    print(f"  Outside all:     {total_outside:,}")
    print(f"  Multiple matches: {total_multiple:,}")
    print(f"  Time:            {elapsed:.0f}s ({total_processed/elapsed:.0f} rec/s)")

    print(f"\n  === Newly tagged by country (top 20) ===")
    for country, cnt in sorted(country_new.items(), key=lambda x: -x[1])[:20]:
        print(f"    {country:10s} {cnt:>7,}")

    print(f"\n  === Outside all boundaries by country (top 20) ===")
    for country, cnt in sorted(country_outside.items(), key=lambda x: -x[1])[:20]:
        print(f"    {country:10s} {cnt:>7,}")

    # Log provenance
    if provenance_rec is not None:
        provenance_rec.__exit__(None, None, None)

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

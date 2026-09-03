#!/usr/bin/env python3
"""
USDA Food Desert Enrichment
============================
Enriches church records with USDA Food Access Research Atlas data at the
census-tract level. Adds food desert indicators: low-income/low-access
classification, distance to supermarket, vehicle access, and more.

Data: USDA ERS Food Access Research Atlas (2019, updated 2021)
Join key: tract_fips (11-digit Census Tract FIPS)

Columns added (prefixed with food_desert_):
  food_desert_low_inc_low_access_1_10 — Classic "food desert" flag (1mi urban / 10mi rural)
  food_desert_low_inc_low_access_vehicle — Low-income + no vehicle access
  food_desert_low_inc_tract — Tract is low-income
  food_desert_poverty_rate — Tract poverty rate
  food_desert_low_access_1 — Low access at 1 mile
  food_desert_low_access_10 — Low access at 10 miles
  food_desert_low_access_20 — Low access at 20 miles
  food_desert_low_access_half — Low access at 1/2 mile
  food_desert_low_access_vehicle — Low access by vehicle availability
  food_desert_urban — Urban flag (1=rural, 2=urban)
  food_desert_group_quarters — Has group quarters population
  food_desert_no_vehicle_hh — Households with no vehicle
  food_desert_snap_hh — SNAP-receiving households
  food_desert_population — Total population (2010)
  food_desert_median_family_income — Median family income

Usage:
    python scripts/enrichment/enrich_food_desert.py
    python scripts/enrichment/enrich_food_desert.py --dry-run
    python scripts/enrichment/enrich_food_desert.py --force-download
"""

import os, sys, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_DIR)

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# Columns to add (USDA name -> DB column name)
COLUMN_MAP = {
    "LILATracts_1And10": "food_desert_low_inc_low_access_1_10",
    "LILATracts_halfAnd10": "food_desert_low_inc_low_access_half_10",
    "LILATracts_1And20": "food_desert_low_inc_low_access_1_20",
    "LILATracts_Vehicle": "food_desert_low_inc_low_access_vehicle",
    "HUNVFlag": "food_desert_no_vehicle_flag",
    "LowIncomeTracts": "food_desert_low_inc_tract",
    "PovertyRate": "food_desert_poverty_rate",
    "MedianFamilyIncome": "food_desert_median_family_income",
    "Urban": "food_desert_urban",
    "LA1and10": "food_desert_low_access_1_10",
    "LAhalfand10": "food_desert_low_access_half_10",
    "LATracts_half": "food_desert_low_access_half",
    "LATracts1": "food_desert_low_access_1",
    "LATracts10": "food_desert_low_access_10",
    "LATracts20": "food_desert_low_access_20",
    "LATractsVehicle_20": "food_desert_low_access_vehicle",
    "GroupQuartersFlag": "food_desert_group_quarters",
    "TractHUNV": "food_desert_no_vehicle_hh",
    "TractSNAP": "food_desert_snap_hh",
    "TractKids": "food_desert_kids_pop",
    "TractSeniors": "food_desert_seniors_pop",
    "Pop2010": "food_desert_population",
    "OHU2010": "food_desert_ohu",
}

# Integer columns (for ALTER TABLE)
COL_TYPES = {
    "food_desert_low_inc_low_access_1_10": "INTEGER",
    "food_desert_low_inc_low_access_half_10": "INTEGER",
    "food_desert_low_inc_low_access_1_20": "INTEGER",
    "food_desert_low_inc_low_access_vehicle": "INTEGER",
    "food_desert_no_vehicle_flag": "INTEGER",
    "food_desert_low_inc_tract": "INTEGER",
    "food_desert_poverty_rate": "REAL",
    "food_desert_median_family_income": "INTEGER",
    "food_desert_urban": "INTEGER",
    "food_desert_low_access_1_10": "INTEGER",
    "food_desert_low_access_half_10": "INTEGER",
    "food_desert_low_access_half": "INTEGER",
    "food_desert_low_access_1": "INTEGER",
    "food_desert_low_access_10": "INTEGER",
    "food_desert_low_access_20": "INTEGER",
    "food_desert_low_access_vehicle": "INTEGER",
    "food_desert_group_quarters": "INTEGER",
    "food_desert_no_vehicle_hh": "INTEGER",
    "food_desert_snap_hh": "INTEGER",
    "food_desert_kids_pop": "INTEGER",
    "food_desert_seniors_pop": "INTEGER",
    "food_desert_population": "INTEGER",
    "food_desert_ohu": "INTEGER",
}


def get_db():
    import sqlite3
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def ensure_columns(db):
    """Add food desert columns if missing."""
    cur = db.execute("PRAGMA table_info(churches)")
    existing = {c[1] for c in cur.fetchall()}
    added = 0
    for col, typ in COL_TYPES.items():
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {typ}")
            added += 1
    db.commit()
    return added


def load_fara_data(dry_run=False, force_download=False):
    """Load FARA data via market loader."""
    from gw_geo.market import load_food_desert
    print("  Loading Food Access Research Atlas data...")
    t0 = time.time()
    records = load_food_desert(force=force_download)
    if not records:
        print("  ERROR: No FARA data loaded!")
        return None
    print(f"  Loaded {len(records):,} tracts in {time.time()-t0:.1f}s")

    # Build lookup by CensusTract
    lookup = {}
    for r in records:
        tract = r.get("CensusTract", "").strip()
        if tract:
            lookup[tract] = r
    print(f"  Lookup has {len(lookup):,} unique tracts")
    return lookup


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrich churches with USDA food desert data")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be updated without writing")
    parser.add_argument("--force-download", action="store_true", help="Re-download FARA data")
    args = parser.parse_args()

    print("=" * 60)
    print("USDA Food Desert Enrichment")
    print("=" * 60)

    # Load FARA data
    fara = load_fara_data(dry_run=args.dry_run, force_download=args.force_download)
    if fara is None:
        print("Aborting.")
        return

    # Connect to DB
    db = get_db()
    cols_added = ensure_columns(db)
    print(f"  Added {cols_added} new columns")

    # Get churches with tract_fips
    cur = db.execute("""
        SELECT id, tract_fips
        FROM churches
        WHERE tract_fips IS NOT NULL AND tract_fips != ''
    """)
    rows = cur.fetchall()
    print(f"  Churches with tract FIPS: {len(rows):,}")

    if args.dry_run:
        # Count matches
        matched = sum(1 for r in rows if r["tract_fips"] in fara)
        print(f"\n  DRY RUN: {matched:,} of {len(rows):,} would be enriched")
        print(f"  Unmatched: {len(rows)-matched:,} tracts not found in FARA")

        # Show some matched examples
        print("\n  === Sample matches ===")
        count = 0
        for r in rows:
            tract = r["tract_fips"]
            if tract in fara and count < 10:
                fd = fara[tract]
                lilac = fd.get("LILATracts_1And10", "")
                urban = fd.get("Urban", "")
                print(f"    ID={r['id']:>8}  tract={tract}  food_desert={lilac}  urban={urban}")
                count += 1
        db.close()
        return

    # Do the enrichment
    start = time.time()
    updated = 0
    skipped = 0
    batch = []
    BATCH_SIZE = 500

    for r in rows:
        tract = r["tract_fips"]
        if tract not in fara:
            skipped += 1
            continue

        fd = fara[tract]
        sets = []
        vals = []

        for usda_col, db_col in COLUMN_MAP.items():
            raw_val = fd.get(usda_col, "")
            # Convert empty strings to None
            val = None if raw_val == "" else raw_val
            try:
                if COL_TYPES.get(db_col) == "INTEGER" and val is not None:
                    val = int(float(val))
                elif COL_TYPES.get(db_col) == "REAL" and val is not None:
                    val = float(val)
            except (ValueError, TypeError):
                val = None
            sets.append(f"{db_col} = ?")
            vals.append(val)

        vals.append(r["id"])
        batch.append((sets, vals))

        if len(batch) >= BATCH_SIZE:
            _execute_batch(db, batch)
            updated += len(batch)
            elapsed = time.time() - start
            print(f"  Updated {updated:,} | {updated/max(elapsed,1):.0f}/s")
            batch = []

    if batch:
        _execute_batch(db, batch)
        updated += len(batch)

    elapsed = time.time() - start
    print(f"\n{'=' * 60}")
    print(f"Done! {updated:,} churches enriched in {elapsed:.0f}s")
    print(f"  Skipped (no tract match): {skipped:,}")
    print(f"  Avg rate: {updated/max(elapsed,1):.0f}/s")

    # Stats
    print(f"\n=== Food Desert Stats ===")
    cur = db.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN food_desert_low_inc_low_access_1_10 = 1 THEN 1 END) as food_desert,
            COUNT(CASE WHEN food_desert_urban = 1 THEN 1 END) as rural,
            COUNT(CASE WHEN food_desert_urban = 2 THEN 1 END) as urban,
            AVG(CASE WHEN food_desert_poverty_rate IS NOT NULL THEN food_desert_poverty_rate END) as avg_poverty
        FROM churches
        WHERE food_desert_low_inc_low_access_1_10 IS NOT NULL
    """)
    s = cur.fetchone()
    print(f"  Churches in food desert tracts: {s['food_desert']:,}")
    print(f"  Rural tracts: {s['rural']:,}  Urban: {s['urban']:,}")
    print(f"  Avg tract poverty rate: {s['avg_poverty']:.1f}%" if s['avg_poverty'] else "  Avg tract poverty rate: N/A")

    db.close()


def _execute_batch(db, batch):
    """Execute a batch of UPDATEs."""
    sql = "UPDATE churches SET " + ", ".join(batch[0][0]) + " WHERE id = ?"
    db.executemany(sql, [vals for _, vals in batch])
    db.commit()


if __name__ == "__main__":
    main()

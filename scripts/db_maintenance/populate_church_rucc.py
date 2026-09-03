"""
SCRIPT: populate_rucc_codes.py
PURPOSE:
  Create/refresh the standalone rucc_codes reference table (county FIPS → RUCC 2023).
  
  Data flow:
    1. Read USDA RUCC CSV → structured county records
    2. Create/populate rucc_codes table

  Usage: churches JOIN on county_fips_5:
    SELECT ch.*, rc.rucc_code, rc.description
    FROM churches ch
    LEFT JOIN rucc_codes rc ON ch.county_fips_5 = rc.fips

  Source: USDA ERS 2023 Rural-Urban Continuum Codes
    https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/

USAGE:
    python scripts/db_maintenance/populate_rucc_codes.py
    python scripts/db_maintenance/populate_rucc_codes.py --dry-run
"""

import argparse
import csv
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gw_db import connect, Provenance

DB_PATH = "churches.db"
RUCC_CSV = "data/rucc2023.csv"


def load_rucc_records(csv_path: str) -> list[dict]:
    """Load USDA RUCC CSV into structured county records."""
    rows = {}
    with open(csv_path, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = row["FIPS"].strip()
            if fips not in rows:
                rows[fips] = {
                    "fips": fips,
                    "state": row["State"].strip(),
                    "county_name": row["County_Name"].strip(),
                }
            attr = row["Attribute"].strip()
            val = row["Value"].strip()
            if attr == "RUCC_2023":
                rows[fips]["rucc_code"] = int(val)
            elif attr == "Description":
                rows[fips]["description"] = val
    result = [r for r in rows.values() if "rucc_code" in r]
    print(f"  Loaded {len(result):,} county RUCC records")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Create/refresh rucc_codes reference table from USDA RUCC data"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts and exit")
    parser.add_argument(
        "--rucc-csv", default=RUCC_CSV, help=f"Path to RUCC CSV (default: {RUCC_CSV})"
    )
    args = parser.parse_args()

    db = connect(DB_PATH)
    c = db.cursor()

    print("=== rucc_codes Reference Table ===\n")

    # ─── Step 1: Load RUCC data ──────────────────────────────────────────
    print("Loading RUCC county data...")
    if not os.path.exists(args.rucc_csv):
        print(f"ERROR: RUCC CSV not found at {args.rucc_csv}")
        print("Download from: https://www.ers.usda.gov/media/5768/2023-rural-urban-continuum-codes.csv")
        sys.exit(1)

    records = load_rucc_records(args.rucc_csv)

    if args.dry_run:
        print(f"\n  Records: {len(records):,}")
        codes = set(r["rucc_code"] for r in records)
        print(f"  RUCC codes: {sorted(codes)}")
        return

    # ─── Step 2: Create table ────────────────────────────────────────────
    print("Creating/replacing rucc_codes table...")
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rucc_codes'")
    if c.fetchone():
        db.execute("DROP TABLE rucc_codes")
        db.commit()

    db.execute("""
        CREATE TABLE rucc_codes (
            fips            TEXT PRIMARY KEY,
            state           TEXT NOT NULL,
            county_name     TEXT NOT NULL,
            rucc_code       INTEGER NOT NULL CHECK(rucc_code BETWEEN 1 AND 9),
            description     TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    db.commit()

    # ─── Step 3: Populate ────────────────────────────────────────────────
    db.executemany(
        "INSERT INTO rucc_codes (fips, state, county_name, rucc_code, description) "
        "VALUES (:fips, :state, :county_name, :rucc_code, :description)",
        records,
    )
    db.commit()

    c.execute("SELECT COUNT(*) FROM rucc_codes")
    cnt = c.fetchone()[0]
    print(f"  Populated: {cnt:,} rows")

    # Index
    db.execute("CREATE INDEX IF NOT EXISTS idx_rucc_codes_fips ON rucc_codes(fips)")
    db.commit()

    # Summary
    c.execute(
        "SELECT rucc_code, description, COUNT(*) FROM rucc_codes "
        "GROUP BY rucc_code ORDER BY rucc_code"
    )
    print("\n=== RUCC Distribution (counties) ===")
    for row in c.fetchall():
        print(f"  Code {row[0]} ({row[1]}): {row[2]:,} counties")

    # Church coverage
    c.execute(
        "SELECT rc.rucc_code, rc.description, COUNT(*) as churches "
        "FROM churches ch "
        "JOIN rucc_codes rc ON ch.county_fips_5 = rc.fips "
        "GROUP BY rc.rucc_code ORDER BY rc.rucc_code"
    )
    print("\n=== Churches by RUCC Code ===")
    total_churches = 0
    for row in c.fetchall():
        total_churches += row[2]
        print(f"  Code {row[0]}: {row[2]:,} churches — {row[1]}")
    print(f"  Total: {total_churches:,} churches with RUCC assignments")

    # ─── Provenance ──────────────────────────────────────────────────────
    with Provenance(
        conn=db,
        source="usda_rucc_2023",
        script_name="populate_rucc_codes.py",
        action="enriched",
        fields="fips, state, county_name, rucc_code, description",
        params=f"Standalone rucc_codes table. {cnt:,} counties, {total_churches:,} churches matchable.",
    ) as p:
        p.churches_updated = 0

    print("\nDone.")


if __name__ == "__main__":
    main()

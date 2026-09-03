"""
Create standalone rucc_codes reference table from USDA RUCC 2023 data.
Replaces the old per-church church_rucc bridge table.

Design:
  rucc_codes = county-level lookup: county FIPS → RUCC code + description
  Churches already have county_fips_5 column, so any query can JOIN:
    SELECT ch.*, rc.rucc_code, rc.description
    FROM churches ch
    LEFT JOIN rucc_codes rc ON ch.county_fips_5 = rc.fips

Usage:
    python _create_rucc_codes.py
    python _create_rucc_codes.py --dry-run
"""

import argparse
import csv
import sqlite3
import sys
import os

DB_PATH = "churches.db"
RUCC_CSV = "data/rucc2023.csv"


def load_rucc_csv(csv_path: str) -> list[dict]:
    """Load USDA RUCC CSV into structured rows (one per county)."""
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
    print(f"  Loaded {len(result):,} county RUCC records from CSV")
    return result


def create_table(conn: sqlite3.Connection, data: list[dict], dry_run: bool = False):
    """Create and populate the rucc_codes reference table."""
    c = conn.cursor()

    # Drop old church_rucc if it exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='church_rucc'")
    if c.fetchone():
        print("  Dropping old church_rucc table (replaced by rucc_codes JOIN)...")
        if not dry_run:
            c.execute("DROP TABLE church_rucc")
            conn.commit()
            print("    Dropped.")

    # Create rucc_codes table
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rucc_codes'")
    if c.fetchone():
        print("  rucc_codes table already exists, recreating...")
        if not dry_run:
            c.execute("DROP TABLE rucc_codes")
            conn.commit()

    print("  Creating rucc_codes table...")
    if not dry_run:
        c.execute("""
            CREATE TABLE rucc_codes (
                fips            TEXT PRIMARY KEY,
                state           TEXT NOT NULL,
                county_name     TEXT NOT NULL,
                rucc_code       INTEGER NOT NULL CHECK(rucc_code BETWEEN 1 AND 9),
                description     TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()
        print("    Created.")

        # Populate
        c.executemany(
            "INSERT INTO rucc_codes (fips, state, county_name, rucc_code, description) "
            "VALUES (:fips, :state, :county_name, :rucc_code, :description)",
            data,
        )
        conn.commit()

        c.execute("SELECT COUNT(*) FROM rucc_codes")
        cnt = c.fetchone()[0]
        print(f"    Populated: {cnt:,} rows")

        # Show distribution
        c.execute(
            "SELECT rucc_code, description, COUNT(*) FROM rucc_codes "
            "GROUP BY rucc_code ORDER BY rucc_code"
        )
        print("\n  RUCC Distribution (counties):")
        for row in c.fetchall():
            print(f"    Code {row[0]} ({row[1]}): {row[2]:,} counties")

        # Create index for fast JOIN
        c.execute("CREATE INDEX IF NOT EXISTS idx_rucc_codes_fips ON rucc_codes(fips)")
        conn.commit()
        print("  Index on fips created.")

        # Show example query
        c.execute(
            "SELECT rc.rucc_code, rc.description, COUNT(*) as churches "
            "FROM churches ch "
            "JOIN rucc_codes rc ON ch.county_fips_5 = rc.fips "
            "GROUP BY rc.rucc_code "
            "ORDER BY rc.rucc_code"
        )
        print("\n  Churches by RUCC code (via county_fips_5 JOIN):")
        has_data = False
        for row in c.fetchall():
            has_data = True
            print(f"    Code {row[0]}: {row[2]:,} churches — {row[1]}")
        if not has_data:
            print("    (no matches — county_fips_5 might need population)")

        # Provenance log
        from gw_db import Provenance
        with Provenance(
            conn=conn,
            source="usda_rucc_2023",
            script_name="_create_rucc_codes.py",
            action="enriched",
            fields="fips, state, county_name, rucc_code, description",
            params=f"Standalone rucc_codes table created with {cnt:,} county records. church_rucc dropped.",
        ) as p:
            p.churches_updated = 0
    else:
        print("    (dry run — skipped)")


def main():
    parser = argparse.ArgumentParser(
        description="Create standalone rucc_codes reference table"
    )
    parser.add_argument("--dry-run", action="store_true", help="Print counts and exit")
    args = parser.parse_args()

    print("=== Create rucc_codes Reference Table ===\n")

    if not os.path.exists(RUCC_CSV):
        print(f"ERROR: RUCC CSV not found at {RUCC_CSV}")
        sys.exit(1)

    data = load_rucc_csv(RUCC_CSV)

    # Preview
    print(f"\n  Sample: {data[0]['fips']} | {data[0]['state']} | {data[0]['county_name']} | Code {data[0]['rucc_code']} | {data[0].get('description','')[:60]}")
    print(f"  Sample: {data[-1]['fips']} | {data[-1]['state']} | {data[-1]['county_name']} | Code {data[-1]['rucc_code']} | {data[-1].get('description','')[:60]}")

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA busy_timeout=30000")

    try:
        create_table(db, data, dry_run=args.dry_run)
    finally:
        db.close()

    print("\nDone.")


if __name__ == "__main__":
    main()

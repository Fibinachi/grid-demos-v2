"""
IRS Migration & High Income Ingestion
=====================================
Downloads and loads:
1. County-to-county migration data (2021-2022, latest available)
2. High-income ZIP data (returns $200K+)

Key sales use: "Where are affluent families moving? Plant churches there."
"""
import sqlite3, csv, io, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT / "data" / "irs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = PROJECT / "churches.db"

# ── Migration data: county inflow ──
# IRS publishes county-to-county migration: county_inflow.csv, county_outflow.csv
# URL: https://www.irs.gov/pub/irs-soi/countyinflow2122.csv
MIGRATION_INFLOW_URL = "https://www.irs.gov/pub/irs-soi/countyinflow2122.csv"
MIGRATION_OUTFLOW_URL = "https://www.irs.gov/pub/irs-soi/countyoutflow2122.csv"

# ── High income ZIP data ──
# IRS publishes top-level ZIP data including high-income brackets
# We already have this in irs_zip_data (AGI brackets 5=$100-200K, 6=$200K+)
# But there's also a dedicated high-income return dataset by ZIP
# URL: part of the ZIP data we already loaded, but we can build a summary view

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

def download_file(url, fname):
    path = DATA_DIR / fname
    if not path.exists():
        print(f"  Downloading {fname} ...", end="", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                path.write_bytes(resp.read())
            print(f" {path.stat().st_size/1e6:.1f}MB")
        except Exception as e:
            print(f" FAILED: {e}")
            return None
    return path

def load_migration(db):
    """Load county-to-county migration inflow/outflow data."""
    print("\n  === MIGRATION DATA ===")

    # Create table
    db.execute("""
        CREATE TABLE IF NOT EXISTS irs_migration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_range TEXT NOT NULL,
            direction TEXT NOT NULL,   -- 'inflow' or 'outflow'
            origin_fips TEXT,           -- origin county FIPS
            origin_state TEXT,
            origin_county TEXT,
            dest_fips TEXT,             -- destination county FIPS
            dest_state TEXT,
            dest_county TEXT,
            return_count INTEGER,       -- number of tax returns
            exemption_count INTEGER,    -- number of exemptions (people proxy)
            agi_amount_k INTEGER,       -- AGI in thousands
            loaded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_mig_origin ON irs_migration(origin_fips)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_mig_dest ON irs_migration(dest_fips)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_mig_year ON irs_migration(year_range)")
    db.commit()

    for direction, url in [("inflow", MIGRATION_INFLOW_URL), ("outflow", MIGRATION_OUTFLOW_URL)]:
        fname = f"irs_migration_{direction}_2122.csv"
        path = download_file(url, fname)
        if not path:
            continue

        # Read and parse
        print(f"  Parsing {direction} ...")
        rows = []
        with open(path, "r", encoding="latin-1") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({
                    "year_range": "2021-2022",
                    "direction": direction,
                    "origin_fips": (row.get("y1_statefips", "") or "") + (row.get("y1_countyfips", "") or ""),
                    "origin_state": row.get("y1_state", "") or "",
                    "origin_county": row.get("y1_countyname", "") or "",
                    "dest_fips": (row.get("y2_statefips", "") or "") + (row.get("y2_countyfips", "") or ""),
                    "dest_state": row.get("y2_state", "") or "",
                    "dest_county": row.get("y2_countyname", "") or "",
                    "return_count": int(float(row.get("n1", 0) or 0)),
                    "exemption_count": int(float(row.get("n2", 0) or 0)),
                    "agi_amount_k": int(float(row.get("agi", 0) or 0)),
                })

        # Batch insert
        db.execute(f"DELETE FROM irs_migration WHERE direction=? AND year_range='2021-2022'", (direction,))
        db.commit()

        sql = """INSERT INTO irs_migration
            (year_range, direction, origin_fips, origin_state, origin_county,
             dest_fips, dest_state, dest_county, return_count, exemption_count, agi_amount_k)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)"""

        batch = []
        start = time.time()
        total = len(rows)
        for i, r in enumerate(rows):
            batch.append((
                r["year_range"], r["direction"], r["origin_fips"], r["origin_state"],
                r["origin_county"], r["dest_fips"], r["dest_state"], r["dest_county"],
                r["return_count"], r["exemption_count"], r["agi_amount_k"]
            ))
            if len(batch) >= 5000:
                db.executemany(sql, batch)
                db.commit()
                batch = []
                progress_bar(i, total, start)
        if batch:
            db.executemany(sql, batch)
            db.commit()
        elapsed = time.time() - start
        progress_bar(total - 1, total, start, f"done {elapsed:.0f}s")
        print()

    # Stats
    cur = db.execute("SELECT direction, COUNT(*), SUM(return_count) FROM irs_migration GROUP BY direction")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]:,} county pairs, {r[2]:,} returns")

def build_high_income_view(db):
    """Build a high-income ZIP summary view from irs_zip_data."""
    print("\n  === HIGH INCOME DATA ===")

    # Check if irs_zip_data exists
    cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='irs_zip_data'")
    if not cur.fetchone():
        print("  irs_zip_data not found. Run ingest_irs_zip.py first.")
        return

    db.execute("DROP VIEW IF EXISTS irs_high_income_zip")
    db.execute("""
        CREATE VIEW irs_high_income_zip AS
        SELECT
            zipcode,
            state_fips,
            state_abbr,
            SUM(CASE WHEN agi_bracket = 5 THEN return_count ELSE 0 END) AS bracket_100k_200k_returns,
            SUM(CASE WHEN agi_bracket = 6 THEN return_count ELSE 0 END) AS bracket_200k_plus_returns,
            SUM(CASE WHEN agi_bracket IN (5,6) THEN return_count ELSE 0 END) AS high_income_returns,
            SUM(CASE WHEN agi_bracket IN (5,6) THEN agi_amount_k ELSE 0 END) AS high_income_agi_k,
            SUM(CASE WHEN agi_bracket IN (5,6) THEN charitable_contrib_k ELSE 0 END) AS high_income_charitable_k,
            SUM(CASE WHEN agi_bracket IN (5,6) THEN dependent_count ELSE 0 END) AS high_income_dependents,
            SUM(return_count) AS total_returns,
            CAST(SUM(CASE WHEN agi_bracket IN (5,6) THEN return_count ELSE 0 END) AS REAL)
                / NULLIF(SUM(return_count), 0) * 100 AS high_income_pct
        FROM irs_zip_data
        WHERE tax_year = 2022
        GROUP BY zipcode
        HAVING high_income_returns > 0
    """)
    db.commit()

    cur = db.execute("SELECT COUNT(*) FROM irs_high_income_zip")
    zip_count = cur.fetchone()[0]
    print(f"  high_income_zip view: {zip_count:,} ZIPs with $100K+ returns")

def build_migration_summary(db):
    """Build a county-level migration summary view."""
    db.execute("DROP VIEW IF EXISTS irs_migration_summary")
    db.execute("""
        CREATE VIEW irs_migration_summary AS
        SELECT
            dest_fips AS county_fips,
            dest_state AS state,
            dest_county AS county,
            SUM(return_count) AS inflow_returns,
            SUM(exemption_count) AS inflow_people,
            SUM(agi_amount_k) AS inflow_agi_k,
            CAST(SUM(agi_amount_k) AS REAL) / NULLIF(SUM(return_count), 0) AS inflow_avg_agi_k
        FROM irs_migration
        WHERE direction = 'inflow' AND year_range = '2021-2022'
        GROUP BY dest_fips
    """)
    db.commit()

    cur = db.execute("SELECT COUNT(*) FROM irs_migration_summary")
    print(f"  migration_summary view: {cur.fetchone()[0]:,} counties with inflow data")

def main():
    print(f"\n{'='*60}")
    print(f"  IRS Migration + High Income Ingestion")
    print(f"{'='*60}")

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")

    load_migration(db)
    build_high_income_view(db)
    build_migration_summary(db)

    # Log provenance
    db.execute("""
        INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, status, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "irs_soi", "ingest_irs_migration.py",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "completed",
        "County-to-county migration inflow/outflow 2021-2022. High-income ZIP view."
    ))
    db.commit()
    db.close()

    print(f"\n{'='*60}")
    print(f"  Done! irs_migration + irs_high_income_zip ready.")
    print(f"  Join churches via: c.county_fips_5 = m.county_fips (migration)")
    print(f"  Join churches via: c.zip5 = h.zipcode (high income)")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

"""
IRS SOI ZIP Code Data Ingestion
================================
Downloads 2022 IRS tax data by ZIP code and builds irs_zip_data table.
Joins to churches via zip5 column for ZIP-level financial context.

Key fields: AGI, charitable contributions, dependents (children proxy),
salaries, capital gains, itemized deductions — all by AGI bracket within ZIP.

Usage:
  python scripts/enrichment/ingest_irs_zip.py
  python scripts/enrichment/ingest_irs_zip.py --year 2022
"""
import argparse, sqlite3, csv, io, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT / "data" / "irs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = PROJECT / "churches.db"

IRS_URL = "https://www.irs.gov/pub/irs-soi/22zpallagi.csv"

# Columns we care about (from IRS SOI documentation)
# The CSV has ~150 columns; we extract the valuable ones
KEEP_COLS = {
    "STATEFIPS": "state_fips",
    "STATE": "state_abbr",
    "zipcode": "zipcode",
    "agi_stub": "agi_bracket",
    "N1": "return_count",
    "mars1": "single_count",
    "MARS2": "joint_count",
    "MARS4": "head_household_count",
    "N2": "exemption_count",
    "DIR_DEP": "dependent_count",
    "A00100": "agi_amount_k",
    "A02650": "total_income_k",
    "A00200": "wages_k",
    "A00300": "interest_k",
    "A00600": "dividends_k",
    "A00900": "business_income_k",
    "A01000": "capital_gains_k",
    "A02300": "unemployment_k",
    "A02500": "social_security_k",
    "A18300": "charitable_contrib_k",
    "A04470": "itemized_deductions_k",
    "A04800": "taxable_income_k",
    "A05800": "total_tax_k",
    "N07100": "credit_return_count",
    "A07100": "total_credits_k",
    "ELDERLY": "elderly_count",
}

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

def download_and_parse():
    """Download IRS CSV and parse into list of dicts."""
    csv_path = DATA_DIR / "irs_zip_2022.csv"

    if not csv_path.exists():
        print(f"  Downloading {IRS_URL} ...", end="", flush=True)
        req = urllib.request.Request(IRS_URL, headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            csv_path.write_bytes(resp.read())
        print(f" {csv_path.stat().st_size/1e6:.1f}MB")

    print(f"  Parsing CSV ({csv_path.stat().st_size/1e6:.0f}MB) ...")
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filtered = {}
            for irs_col, our_col in KEEP_COLS.items():
                if irs_col in row:
                    val = row[irs_col].strip()
                    # Convert numeric fields (IRS uses decimals like "109460.0000")
                    if our_col.endswith("_count") or our_col.endswith("_k"):
                        try:
                            val = int(float(val)) if val else 0
                        except (ValueError, TypeError):
                            val = 0
                    filtered[our_col] = val
            if filtered.get("zipcode") and filtered["zipcode"] != "00000":
                rows.append(filtered)
    print(f"  Parsed {len(rows):,} rows across {len(set(r['zipcode'] for r in rows)):,} ZIP codes")
    return rows

def create_table(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS irs_zip_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zipcode TEXT NOT NULL,
            state_fips TEXT,
            state_abbr TEXT,
            agi_bracket INTEGER NOT NULL,
            return_count INTEGER,
            single_count INTEGER,
            joint_count INTEGER,
            head_household_count INTEGER,
            exemption_count INTEGER,
            dependent_count INTEGER,
            agi_amount_k INTEGER,
            total_income_k INTEGER,
            wages_k INTEGER,
            interest_k INTEGER,
            dividends_k INTEGER,
            business_income_k INTEGER,
            capital_gains_k INTEGER,
            unemployment_k INTEGER,
            social_security_k INTEGER,
            charitable_contrib_k INTEGER,
            itemized_deductions_k INTEGER,
            taxable_income_k INTEGER,
            total_tax_k INTEGER,
            credit_return_count INTEGER,
            total_credits_k INTEGER,
            elderly_count INTEGER,
            tax_year INTEGER DEFAULT 2022,
            loaded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_irs_zip ON irs_zip_data(zipcode)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_irs_zip_bracket ON irs_zip_data(zipcode, agi_bracket)")
    db.commit()

def load_into_db(db, rows):
    """Batch insert IRS data."""
    db.execute("DELETE FROM irs_zip_data WHERE tax_year=2022")
    db.commit()

    cols = list(KEEP_COLS.values())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO irs_zip_data ({','.join(cols)},tax_year) VALUES ({placeholders},2022)"

    batch = []
    start = time.time()
    total = len(rows)

    for i, r in enumerate(rows):
        batch.append(tuple(r.get(c, 0) for c in cols))
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

def build_zip_summary(db):
    """Create a denormalized ZIP-level summary (collapses AGI brackets)."""
    print("  Building ZIP-level summary view ...")
    db.execute("DROP VIEW IF EXISTS irs_zip_summary")
    db.execute("""
        CREATE VIEW irs_zip_summary AS
        SELECT
            zipcode,
            state_fips,
            state_abbr,
            SUM(return_count) AS total_returns,
            SUM(dependent_count) AS total_dependents,
            SUM(exemption_count) AS total_exemptions,
            SUM(agi_amount_k) AS total_agi_k,
            SUM(total_income_k) AS total_income_k,
            SUM(wages_k) AS total_wages_k,
            SUM(charitable_contrib_k) AS total_charitable_k,
            SUM(itemized_deductions_k) AS total_itemized_k,
            SUM(taxable_income_k) AS total_taxable_k,
            SUM(total_tax_k) AS total_tax_k,
            SUM(capital_gains_k) AS total_capital_gains_k,
            SUM(elderly_count) AS total_elderly,
            SUM(CASE WHEN agi_bracket IN (5,6) THEN return_count ELSE 0 END) AS high_income_returns,
            SUM(CASE WHEN agi_bracket IN (1,2) THEN return_count ELSE 0 END) AS low_income_returns,
            CAST(SUM(dependent_count) AS REAL) / NULLIF(SUM(return_count), 0) AS dependents_per_return,
            CAST(SUM(agi_amount_k) AS REAL) / NULLIF(SUM(return_count), 0) AS avg_agi_k,
            CAST(SUM(charitable_contrib_k) AS REAL) / NULLIF(SUM(return_count), 0) AS avg_charitable_k
        FROM irs_zip_data
        WHERE tax_year = 2022
        GROUP BY zipcode
    """)
    db.commit()
    cur = db.execute("SELECT COUNT(*) FROM irs_zip_summary")
    print(f"  ZIP summary: {cur.fetchone()[0]:,} ZIP codes")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2022", help="Tax year")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  IRS SOI ZIP Data Ingestion — Tax Year {args.year}")
    print(f"{'='*60}")

    rows = download_and_parse()

    db = sqlite3.connect(str(DB_PATH))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=30000")
    create_table(db)
    load_into_db(db, rows)
    build_zip_summary(db)

    # Stats
    cur = db.execute("""
        SELECT COUNT(DISTINCT zipcode), SUM(return_count)
        FROM irs_zip_data WHERE tax_year=2022
    """)
    zips, total_returns = cur.fetchone()
    print(f"\n  Loaded: {zips:,} ZIP codes, {total_returns/1e6:.1f}M returns")

    # Match rate with churches
    cur = db.execute("""
        SELECT COUNT(DISTINCT c.id) FROM churches c
        INNER JOIN irs_zip_data i ON c.zip5 = i.zipcode
        WHERE c.country='US'
    """)
    matched = cur.fetchone()[0]
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND zip5 IS NOT NULL AND zip5 != ''")
    with_zip = cur.fetchone()[0]
    print(f"  Church match rate: {matched:,}/{with_zip:,} ({100*matched/with_zip:.1f}%)")

    # Provenance
    db.execute("""
        INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated,
         fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "irs_soi", "ingest_irs_zip.py",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        0, "irs_zip_data,irs_zip_summary",
        "completed",
        f"Tax year 2022. {zips:,} ZIP codes, {total_returns/1e6:.1f}M returns. "
        f"{matched:,} US churches matched via zip5."
    ))
    db.commit()
    db.close()

    print(f"\n{'='*60}")
    print(f"  Done! irs_zip_data + irs_zip_summary ready.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

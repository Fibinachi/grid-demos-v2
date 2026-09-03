#!/usr/bin/env python3
"""
GrantWizard — EAC EAVS Voter Registration Data Importer
==========================================================
Downloads and imports Election Administration and Voting Survey (EAVS) data
from the U.S. Election Assistance Commission.

Data includes jurisdiction-level voter registration, turnout, and election
administration metrics for 2020, 2022, and 2024.

Join key: county_fips (first 5 digits of EAC's 10-digit FIPSCode)

What EAC EAVS provides:
  Section A — Voter Registration: active/inactive registrations,
               new registrations, list maintenance
  Section F — Voter Participation: ballots counted, turnout estimates
  Section D — Polling Operations: polling places, workers
  Section E — Provisional Ballots

Usage:
    python scripts/enrichment/import_eac_eavs.py
    python scripts/enrichment/import_eac_eavs.py --year 2024
"""

import csv, io, os, sqlite3, sys, urllib.request, zipfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

EAVS_FILES = {
    2024: "https://www.eac.gov/sites/default/files/2026-02/2024_EAVS_for_Public_Release_nolabel_V2_csv.zip",
    2022: "https://www.eac.gov/sites/default/files/2023-12/2022_EAVS_for_Public_Release_nolabel_V1.1_CSV.zip",
    2020: "https://www.eac.gov/sites/default/files/2023-12/2020_EAVS_for_Public_Release_nolabel_V1.2_CSV.zip",
}

# Known EAC sentinel values for missing/NA data
SENTINEL_MISSING = {-88, -99, -77, -66, -55, -44, -33, -22, -11}

# The 5-digit county FIPS is the first 5 chars of the 10-digit FIPSCode
# FIPSCode format: SSCCCJJJJJ where SS=state, CCC=county, JJJJJ=sub-jurisdiction


def safe_int(val, default=None):
    """Parse int, treating EAC sentinel values as None."""
    try:
        v = int(float(str(val).strip()))
        if v in SENTINEL_MISSING:
            return default
        return v
    except (ValueError, TypeError):
        return default


def download_eavs(year):
    """Download EAVS CSV for a given year and return as list of dicts."""
    url = EAVS_FILES.get(year)
    if not url:
        print(f"  No URL configured for {year}")
        return None
    
    print(f"  Downloading {year} EAVS...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            csv_files = [f for f in z.namelist() if f.endswith('.csv')]
            if not csv_files:
                print("No CSV found in zip!")
                return None
            with z.open(csv_files[0]) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                rows = list(reader)
        
        print(f"{len(rows):,} records")
        return rows
    except Exception as e:
        print(f"FAILED: {e}")
        return None


def extract_registration_data(rows, year):
    """
    Extract key registration and turnout variables from EAVS rows.
    
    Key columns extracted:
      - FIPSCode → county_fips (first 5 digits)
      - A1a: Active registered voters
      - A1b: Inactive registered voters
      - A1c: Total active+inactive (may be -99 if not reported)
      - A3a: New registrations accepted
      - A3b: Online new registrations
      - A4a through A4k: List maintenance removals
      - F1a: Total ballots counted (voter turnout)
      - F1b: Election day votes (may be -99)
      - D1a: Number of polling places
      - D2a through D2g: Poll workers
      - E1a: Provisional ballots cast
    
    Also tracks year-specific column name variations.
    """
    out = []
    
    # Column name variations by year
    col_map = {
        "a1a": ["A1a", "A1a_flag"],
        "a1b": ["A1b", "A1b_flag"],
        "a1c": ["A1c"],
        "a3a": ["A3a"],
        "a3b": ["A3b", "A3b_flag"],
        "f1a": ["F1a", "F1a_flag"],
        "d1a": ["D1a", "D1a_flag"],
        "d2a": ["D2a", "D2a_flag"],
        "e1a": ["E1a", "E1a_flag"],
    }
    
    def get_val(row, keys):
        for k in keys:
            v = row.get(k, "")
            if v and v.strip():
                return v.strip()
        return ""
    
    for row in rows:
        fips_raw = row.get("FIPSCode", "").strip()
        if not fips_raw or len(fips_raw) < 5:
            continue
        
        county_fips = fips_raw[:5]  # First 5 chars = state+county FIPS
        
        rec = {
            "year": year,
            "county_fips": county_fips,
            "jurisdiction_name": row.get("Jurisdiction_Name", "").strip(),
            "state": row.get("State_Full", "").strip(),
            "state_abbr": row.get("State_Abbr", "").strip(),
            
            # Voter Registration (Section A)
            "active_reg": safe_int(get_val(row, ["A1a", "A1a_flag"])),
            "inactive_reg": safe_int(get_val(row, ["A1b", "A1b_flag"])),
            "total_reg": safe_int(get_val(row, ["A1c"])),
            "new_registrations": safe_int(get_val(row, ["A3a"])),
            "online_registrations": safe_int(get_val(row, ["A3b", "A3b_flag"])),
            
            # Voter Turnout (Section F)
            "total_ballots": safe_int(get_val(row, ["F1a", "F1a_flag"])),
            
            # Polling Operations (Section D)
            "polling_places": safe_int(get_val(row, ["D1a", "D1a_flag"])),
            "poll_workers": safe_int(get_val(row, ["D2a", "D2a_flag"])),
            
            # Provisional Ballots
            "provisional_ballots": safe_int(get_val(row, ["E1a", "E1a_flag"])),
        }
        
        # Calculate derived: turnout rate
        reg = rec["total_reg"] or (rec["active_reg"] or 0) + (rec["inactive_reg"] or 0)
        ballots = rec["total_ballots"]
        if reg and ballots:
            rec["turnout_rate"] = round(ballots / reg * 100, 2)
        else:
            rec["turnout_rate"] = None
        
        out.append(rec)
    
    return out


def create_table(db):
    """Create the eac_eavs table."""
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eac_eavs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            county_fips TEXT NOT NULL,
            jurisdiction_name TEXT,
            state TEXT,
            state_abbr TEXT,
            active_reg INTEGER,
            inactive_reg INTEGER,
            total_reg INTEGER,
            new_registrations INTEGER,
            online_registrations INTEGER,
            total_ballots INTEGER,
            polling_places INTEGER,
            poll_workers INTEGER,
            provisional_ballots INTEGER,
            turnout_rate REAL,
            UNIQUE(year, county_fips)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_eac_eavs_fips ON eac_eavs(county_fips)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_eac_eavs_year ON eac_eavs(year)")
    db.commit()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import EAC EAVS voter registration data")
    parser.add_argument("--year", type=int, choices=[2020, 2022, 2024], default=None,
                        help="Import only a specific year (default: all)")
    args = parser.parse_args()
    
    years_to_import = [args.year] if args.year else [2024, 2022, 2020]
    
    print("GrantWizard — EAC EAVS Importer")
    print("=" * 40)
    
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    create_table(db)
    cur = db.cursor()
    
    # Check what's already loaded
    cur.execute("SELECT year, COUNT(*) FROM eac_eavs GROUP BY year ORDER BY year")
    existing = {r[0]: r[1] for r in cur.fetchall()}
    if existing:
        print("Existing EAVS data by year:")
        for y, c in sorted(existing.items()):
            print(f"  {y}: {c:,} jurisdictions")
    
    total_imported = 0
    for year in years_to_import:
        if year in existing:
            print(f"\n{year} already loaded ({existing[year]:,} records) — skipping")
            continue
        
        print(f"\n--- {year} ---")
        rows = download_eavs(year)
        if not rows:
            continue
        
        extracted = extract_registration_data(rows, year)
        print(f"  Extracted: {len(extracted):,} county-level records")
        
        # Insert in batches
        inserted = 0
        for i in range(0, len(extracted), 500):
            batch = extracted[i:i+500]
            for d in batch:
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO eac_eavs
                        (year, county_fips, jurisdiction_name, state, state_abbr,
                         active_reg, inactive_reg, total_reg,
                         new_registrations, online_registrations,
                         total_ballots, polling_places, poll_workers,
                         provisional_ballots, turnout_rate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        d["year"], d["county_fips"], d["jurisdiction_name"],
                        d["state"], d["state_abbr"],
                        d["active_reg"], d["inactive_reg"], d["total_reg"],
                        d["new_registrations"], d["online_registrations"],
                        d["total_ballots"], d["polling_places"],
                        d["poll_workers"], d["provisional_ballots"],
                        d["turnout_rate"],
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {d['county_fips']}/{d['year']}: {e}")
            db.commit()
        
        total_imported += inserted
        print(f"  Imported: {inserted:,} jurisdictions for {year}")
    
    # Summary
    print(f"\n=== Import Summary ===")
    print(f"Total records imported this run: {total_imported:,}")
    
    cur.execute("SELECT year, COUNT(*), SUM(active_reg), SUM(total_ballots) FROM eac_eavs WHERE active_reg IS NOT NULL GROUP BY year ORDER BY year")
    print(f"\nEAVS Data Coverage:")
    for year, cnt, tot_reg, tot_bal in cur.fetchall():
        print(f"  {year}: {cnt:,} jurisdictions, {tot_reg:,.0f} registered voters, {tot_bal:,.0f} ballots")
    
    # Show join coverage with churches
    print(f"\n=== Join Coverage: churches ↔ eac_eavs ===")
    for year in [2020, 2022, 2024]:
        cur.execute("""
            SELECT COUNT(*) FROM churches c
            INNER JOIN eac_eavs e ON c.county_fips = e.county_fips
            WHERE e.year = ?
        """, (year,))
        cnt = cur.fetchone()[0]
        print(f"  {year}: {cnt:,} churches joinable ({cnt/325996*100:.1f}%)")
    
    db.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

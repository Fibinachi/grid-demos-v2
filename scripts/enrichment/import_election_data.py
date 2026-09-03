#!/usr/bin/env python3
"""
GrantWizard Election Data Importer
====================================
Downloads county-level presidential election returns from MIT Election Lab
(MEDSL) and loads them into a new `election_results` table.

Cycles: 2000, 2004, 2008, 2012, 2016, 2020, 2024

The data is sourced from the MEDSL (MIT Election Data and Science Lab)
official returns repository on GitHub, which publishes county-level
results under a CC-BY 4.0 license for academic use.

Join key: county_fips (5-digit string: state FIPS + county FIPS)

Usage:
    python scripts/enrichment/import_election_data.py
"""

import csv, io, os, sqlite3, sys, urllib.request, zipfile
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "churches.db")

# MIT Election Lab / MEDSL county-level returns
# "County Presidential Election Returns 2000-2024" (CC0 1.0)
# DOI: 10.7910/DVN/VOQCHQ
# Mirrors (Dataverse requires interactive guestbook):
COUNTY_FILE_URL = "https://minio.lab.sspcloud.fr/lgaliana/data/python-ENSAE/countypres_2000-2024.csv"
COUNTY_FILE_URL_FALLBACK = "https://raw.githubusercontent.com/willmcwain/electoral_college_calculations/b322ae3c0e26f23ed8961e83361d19a4e7df7814/data/countypres_2000-2024.csv"


def download_csv(url, label="data"):
    """Download a CSV from URL and return as list of dicts."""
    print(f"  Downloading {label}...", end=" ", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(raw))
        rows = list(reader)
        print(f"{len(rows):,} rows")
        return rows
    except Exception as e:
        print(f"FAILED: {e}")
        return None


def normalize_medsl_data(rows, year):
    """
    Normalize MEDSL county-level data to a consistent schema.
    
    MEDSL columns vary slightly by year but typically:
      year, state, state_po, county_name, county_fips, office, 
      candidate, party, candidatevotes, totalvotes, ...
    
    We need: county_fips, dem_votes, rep_votes, total_votes, other_votes
    """
    if not rows:
        return []
    
    results = {}
    
    for row in rows:
        raw_fips = row.get("county_fips", "").strip()
        if raw_fips in ("", "NA", "na"):
            continue
        county_fips = raw_fips.zfill(5)
        if county_fips == "00000":
            continue
        
        party = row.get("party", "").strip().lower()
        try:
            candidatevotes = int(float(row.get("candidatevotes", "0").strip() or "0"))
        except (ValueError, TypeError):
            candidatevotes = 0
        try:
            totalvotes = int(float(row.get("totalvotes", "0").strip() or "0"))
        except (ValueError, TypeError):
            totalvotes = 0
        
        if county_fips not in results:
            results[county_fips] = {
                "county_fips": county_fips,
                "year": year,
                "state": row.get("state", "").strip(),
                "county_name": row.get("county_name", "").strip(),
                "dem_votes": 0,
                "rep_votes": 0,
                "other_votes": 0,
                "total_votes": 0,
            }
        
        if party == "democrat":
            results[county_fips]["dem_votes"] += candidatevotes
        elif party == "republican":
            results[county_fips]["rep_votes"] += candidatevotes
        else:
            results[county_fips]["other_votes"] += candidatevotes
        
        results[county_fips]["total_votes"] = max(results[county_fips]["total_votes"], totalvotes)
    
    # Calculate derived columns
    # Shares use (party / total_party_votes) to ensure D+R+O = 100%
    out = []
    for fips, data in results.items():
        total_party = data["dem_votes"] + data["rep_votes"] + data["other_votes"]
        data["total_votes"] = total_party
        data["dem_share"] = round(data["dem_votes"] / total_party * 100, 2) if total_party > 0 else None
        data["rep_share"] = round(data["rep_votes"] / total_party * 100, 2) if total_party > 0 else None
        out.append(data)
    
    return out


def create_table(db):
    """Create the election_results table."""
    cur = db.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS election_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            county_fips TEXT NOT NULL,
            year INTEGER NOT NULL,
            state TEXT,
            county_name TEXT,
            dem_votes INTEGER DEFAULT 0,
            rep_votes INTEGER DEFAULT 0,
            other_votes INTEGER DEFAULT 0,
            total_votes INTEGER DEFAULT 0,
            dem_share REAL,
            rep_share REAL,
            turnout_est REAL,
            UNIQUE(county_fips, year)
        )
    """)
    db.commit()


def main():
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    create_table(db)
    cur = db.cursor()
    
    # Check what's already loaded
    cur.execute("SELECT year, COUNT(*) FROM election_results GROUP BY year ORDER BY year")
    existing = {r[0]: r[1] for r in cur.fetchall()}
    print("Existing election data by year:")
    for y, c in sorted(existing.items()):
        print(f"  {y}: {c:,} counties")
    
    # Download the consolidated 2000-2024 file
    rows = download_csv(COUNTY_FILE_URL, label="SSPCloud mirror")
    if rows is None:
        print("  Trying fallback URL...")
        rows = download_csv(COUNTY_FILE_URL_FALLBACK, label="GitHub mirror")
    if rows is None:
        print("FATAL: Could not download election data from any source")
        db.close()
        return
    
    # Group by year
    from collections import defaultdict
    by_year = defaultdict(list)
    for row in rows:
        year_str = row.get("year", "").strip()
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            continue
        by_year[year].append(row)
    
    print(f"\nYears found in data: {sorted(by_year.keys())}")
    
    years_to_load = sorted(y for y in by_year if y not in existing)
    if not years_to_load:
        print("All years already loaded!")
        db.close()
        return
    
    print(f"Years to load: {years_to_load}")
    
    total_imported = 0
    for year in years_to_load:
        print(f"\n--- {year} ---")
        year_rows = by_year[year]
        print(f"  Raw rows: {len(year_rows):,}")
        
        normalized = normalize_medsl_data(year_rows, year)
        print(f"  Normalized: {len(normalized):,} counties")
        
        # Insert in batches
        inserted = 0
        for i in range(0, len(normalized), 500):
            batch = normalized[i:i+500]
            for d in batch:
                try:
                    cur.execute("""
                        INSERT OR REPLACE INTO election_results
                        (county_fips, year, state, county_name, 
                         dem_votes, rep_votes, other_votes, total_votes,
                         dem_share, rep_share)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        d["county_fips"], d["year"], d["state"], d["county_name"],
                        d["dem_votes"], d["rep_votes"], d["other_votes"], d["total_votes"],
                        d["dem_share"], d["rep_share"],
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {d['county_fips']}/{d['year']}: {e}")
            db.commit()
        
        total_imported += inserted
        print(f"  Imported: {inserted:,} counties for {year}")
    
    # Summary
    print(f"\n=== Import Summary ===")
    print(f"Total records imported: {total_imported:,}")
    cur.execute("SELECT year, COUNT(*) FROM election_results GROUP BY year ORDER BY year")
    for year, cnt in cur.fetchall():
        cur.execute("SELECT SUM(total_votes) FROM election_results WHERE year=?", (year,))
        votes = cur.fetchone()[0] or 0
        print(f"  {year}: {cnt:,} counties, {votes:,.0f} total votes")
    
    db.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

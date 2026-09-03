#!/usr/bin/env python3
"""
Merge ACS/USDA/CDC data from S3 into church DB by county FIPS
==============================================================
Reads census data from S3 bucket, merges by county FIPS code.

Usage:
    python scripts/enrichment/merge_census_data.py

Requires: pip install boto3
"""
import csv, json, os, sqlite3, sys
from datetime import datetime

DB = r'E:\grid\churches.db'
S3_BUCKET = "grantwizard-census-data"
S3_REGION = "us-east-1"

def download_from_s3(key, local_path):
    """Download a file from S3 using AWS CLI."""
    import subprocess
    result = subprocess.run(
        ["aws", "s3", "cp", f"s3://{S3_BUCKET}/{key}", local_path, "--region", S3_REGION],
        capture_output=True, text=True
    )
    return result.returncode == 0

def main():
    import subprocess
    
    print("=" * 60)
    print("Merging Census/ACS Data into Church DB")
    print("=" * 60)
    
    db = sqlite3.connect(DB)
    
    # ── 1. Load ACS county data ──
    print("\n[1] Loading ACS county data from S3...")
    acs_local = r'E:\grid\data\census\acs_2023_county.json'
    if not os.path.exists(acs_local):
        download_from_s3("acs_2023_county.json", acs_local)
    
    with open(acs_local, 'r') as f:
        acs_data = json.load(f)
    
    # First row is headers
    headers = acs_data[0]
    rows = acs_data[1:]
    print(f"  Loaded {len(rows):,} county records with {len(headers)} fields")
    
    # Build county lookup: state+county FIPS -> data
    county_data = {}
    for row in rows:
        row_dict = dict(zip(headers, row))
        state = row_dict.get("state", "")
        county = row_dict.get("county", "")
        fips = state + county  # 5-digit county FIPS
        county_data[fips] = row_dict
    
    print(f"  County lookup: {len(county_data):,} FIPS codes")
    
    # ── 2. Add ACS columns to churches table ──
    print("\n[2] Adding ACS columns to churches table...")
    existing = [r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()]
    
    acs_columns = {
        "acs_total_pop": "INTEGER",
        "acs_median_income": "INTEGER",
        "acs_poverty_universe": "INTEGER",
        "acs_poverty_count": "INTEGER",
        "acs_poverty_rate": "REAL",
        "acs_bachelors_count": "INTEGER",
        "acs_masters_count": "INTEGER",
        "acs_professional_count": "INTEGER",
        "acs_doctorate_count": "INTEGER",
        "acs_employed": "INTEGER",
        "acs_unemployed": "INTEGER",
        "acs_unemployment_rate": "REAL",
        "acs_median_home_value": "INTEGER",
        "acs_median_age": "REAL",
        "acs_white_pop": "INTEGER",
        "acs_black_pop": "INTEGER",
        "acs_native_pop": "INTEGER",
        "acs_asian_pop": "INTEGER",
        "acs_hispanic_pop": "INTEGER",
        "acs_median_income_source": "TEXT",
    }
    
    for col, dtype in acs_columns.items():
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")
            print(f"  Added: {col}")
    
    db.commit()
    
    # ── 3. Merge by FIPS ──
    print("\n[3] Merging ACS data by county FIPS...")
    
    # Variable mapping: ACS header -> DB column
    var_map = {
        "B01001_001E": "acs_total_pop",
        "B19013_001E": "acs_median_income",
        "B17001_001E": "acs_poverty_universe",
        "B17001_002E": "acs_poverty_count",
        "B15003_022E": "acs_bachelors_count",
        "B15003_023E": "acs_masters_count",
        "B15003_024E": "acs_professional_count",
        "B15003_025E": "acs_doctorate_count",
        "B23025_003E": "acs_employed",
        "B23025_005E": "acs_unemployed",
        "B25077_001E": "acs_median_home_value",
        "B01002_001E": "acs_median_age",
        "B02001_002E": "acs_white_pop",
        "B02001_003E": "acs_black_pop",
        "B02001_004E": "acs_native_pop",
        "B02001_005E": "acs_asian_pop",
        "B03003_003E": "acs_hispanic_pop",
    }
    
    updated = 0
    no_fips = 0
    no_match = 0
    
    # Get all churches with FIPS codes
    churches = db.execute("""
        SELECT id, fips FROM churches 
        WHERE fips IS NOT NULL AND fips != '' AND fips != '0'
    """).fetchall()
    
    for cid, fips in churches:
        # Pad FIPS to 5 digits if needed
        fips_padded = fips.zfill(5) if len(fips) < 5 else fips
        
        if fips_padded in county_data:
            row = county_data[fips_padded]
            updates = []
            
            for acs_var, db_col in var_map.items():
                val = row.get(acs_var, "")
                if val and val != "None" and val != "":
                    try:
                        val_int = int(float(val))
                        updates.append(f"{db_col}={val_int}")
                    except:
                        pass
            
            # Calculate derived fields
            # Poverty rate
            try:
                pov_u = int(float(row.get("B17001_001E", 0) or 0))
                pov_c = int(float(row.get("B17001_002E", 0) or 0))
                if pov_u > 0:
                    updates.append(f"acs_poverty_rate={pov_c/pov_u:.4f}")
            except:
                pass
            
            # Unemployment rate
            try:
                emp = int(float(row.get("B23025_003E", 0) or 0))
                unemp = int(float(row.get("B23025_005E", 0) or 0))
                labor = emp + unemp
                if labor > 0:
                    updates.append(f"acs_unemployment_rate={unemp/labor:.4f}")
            except:
                pass
            
            updates.append("acs_median_income_source='acs_2023'")
            
            if updates:
                db.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", (cid,))
                updated += 1
        else:
            no_match += 1
        
        if updated % 10000 == 0:
            db.commit()
            print(f"    Updated {updated:,} churches...")
    
    db.commit()
    
    print(f"\n  Updated: {updated:,} churches")
    print(f"  No FIPS: {no_fips:,}")
    print(f"  No county match: {no_match:,}")
    
    # ── 4. Summary ──
    print(f"\n{'='*50}")
    print("MERGE COMPLETE - Coverage:")
    print(f"{'='*50}")
    
    checks = [
        ("Has ACS median income", "acs_median_income > 0"),
        ("Has ACS poverty data", "acs_poverty_rate > 0"),
        ("Has ACS population", "acs_total_pop > 0"),
        ("Has ACS unemployment", "acs_unemployment_rate > 0"),
    ]
    for label, cond in checks:
        cnt = db.execute(f"SELECT COUNT(*) FROM churches WHERE {cond}").fetchone()[0]
        pct = cnt / 263712 * 100
        print(f"  {label:35s} {cnt:>8,} ({pct:.1f}%)")
    
    # Log to provenance
    db.execute("""
        INSERT INTO provenance_log 
            (source, script_name, completed_at, churches_updated, fields_populated, status, notes)
        VALUES ('acs', 'merge_census_data.py', datetime('now'), ?, 
                'income,poverty,pop,race,education,employment,home_value', 'completed',
                'ACS 5-year 2023 county-level data merged by county FIPS')
    """, (updated,))
    db.commit()
    
    db.close()
    print("\nDone!")

if __name__ == "__main__":
    main()

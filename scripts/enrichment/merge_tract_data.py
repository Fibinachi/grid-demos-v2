#!/usr/bin/env python3
"""
Merge ACS Tract-Level Data into Churches — the big migration
==============================================================
Loads the ACS 5-year 2023 tract-level data (downloaded by download_tract_acs.py)
and merges it onto churches via their 11-digit tract FIPS codes.

This is the payout step: 253K churches with lat/lng → ~74K census tracts →
tract-level income, poverty, education, employment, housing, race, age data.

Column naming:
  All tract-level columns use the tract_ prefix (e.g., tract_acs_median_income).
  The original county-level columns are preserved for backward compatibility.
  A new view `churches_tract_level` is created for convenience.

Workflow:
  1. Load tract ACS JSON
  2. Build tract_fips → demographics lookup
  3. Add tract_* columns to churches table
  4. Join by tract_fips and populate
  5. Report coverage improvements vs county-level

Usage:
    # Full merge
    python scripts/enrichment/merge_tract_data.py

    # Preview only
    python scripts/enrichment/merge_tract_data.py --dry-run

    # Limit for testing
    python scripts/enrichment/merge_tract_data.py --dry-run --limit 10000

Requires:
    python scripts/enrichment/download_tract_acs.py     (run first)
    python scripts/enrichment/tract_reverse_geocode.py   (run first)
"""
import json, os, sqlite3, sys
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
ACS_DATA = os.path.join(PROJECT_DIR, 'data', 'census', 'acs_tract_2023.json')

# Tract-level ACS columns to add
# Format: (column_name, column_type, acs_json_key, description)
TRACT_COLUMNS = [
    # Identity
    ('tract_name', 'TEXT', 'NAME', 'Census tract geographic name'),
    ('tract_state_fips', 'TEXT', 'state_fips', 'State FIPS code'),
    ('tract_county_fips', 'TEXT', 'county', 'County FIPS code'),
    ('tract_code', 'TEXT', 'tract', '6-digit tract code'),
    ('tract_geoid', 'TEXT', 'geoid', '11-digit tract GEOID'),
    
    # Population
    ('tract_acs_total_pop', 'INTEGER', 'B01001_001E', 'Total population in tract'),
    ('tract_acs_race_universe', 'INTEGER', 'B02001_001E', 'Total race population'),
    ('tract_acs_white_pop', 'INTEGER', 'B02001_002E', 'White population in tract'),
    ('tract_acs_black_pop', 'INTEGER', 'B02001_003E', 'Black population in tract'),
    ('tract_acs_native_pop', 'INTEGER', 'B02001_004E', 'Native American population'),
    ('tract_acs_asian_pop', 'INTEGER', 'B02001_005E', 'Asian population'),
    ('tract_acs_hawaiian_pop', 'INTEGER', 'B02001_006E', 'Pacific Islander population'),
    ('tract_acs_hispanic_universe', 'INTEGER', 'B03003_001E', 'Hispanic universe'),
    ('tract_acs_hispanic_pop', 'INTEGER', 'B03003_003E', 'Hispanic/Latino population'),
    
    # Income
    ('tract_acs_median_income', 'INTEGER', 'B19013_001E', 'Median household income ($)'),
    ('tract_acs_gini_index', 'REAL', 'B19083_001E', 'Gini index (income inequality)'),
    
    # Poverty
    ('tract_acs_poverty_universe', 'INTEGER', 'B17001_001E', 'Poverty universe'),
    ('tract_acs_poverty_count', 'INTEGER', 'B17001_002E', 'Below poverty level'),
    ('tract_acs_poverty_family_universe', 'INTEGER', 'B17021_001E', 'Family poverty universe'),
    ('tract_acs_poverty_family_count', 'INTEGER', 'B17021_002E', 'Families below poverty'),
    
    # Education
    ('tract_acs_edu_universe', 'INTEGER', 'B15003_001E', 'Education universe (25+)'),
    ('tract_acs_bachelors_count', 'INTEGER', 'B15003_022E', 'Bachelor\'s degree'),
    ('tract_acs_masters_count', 'INTEGER', 'B15003_023E', 'Master\'s degree'),
    ('tract_acs_professional_count', 'INTEGER', 'B15003_024E', 'Professional degree'),
    ('tract_acs_doctorate_count', 'INTEGER', 'B15003_025E', 'Doctorate degree'),
    
    # Employment
    ('tract_acs_emp_universe', 'INTEGER', 'B23025_001E', 'Employment universe'),
    ('tract_acs_employed', 'INTEGER', 'B23025_003E', 'Employed population'),
    ('tract_acs_unemployed', 'INTEGER', 'B23025_005E', 'Unemployed population'),
    
    # Housing
    ('tract_acs_total_housing', 'INTEGER', 'B25001_001E', 'Total housing units'),
    ('tract_acs_vacant_housing', 'INTEGER', 'B25002_003E', 'Vacant housing units'),
    ('tract_acs_owner_occupied', 'INTEGER', 'B25003_002E', 'Owner-occupied units'),
    ('tract_acs_renter_occupied', 'INTEGER', 'B25003_003E', 'Renter-occupied units'),
    ('tract_acs_median_home_value', 'INTEGER', 'B25077_001E', 'Median home value ($)'),
    
    # Demographics
    ('tract_acs_median_age', 'REAL', 'B01002_001E', 'Median age'),
]

# Derived fields (computed, not directly from ACS)
DERIVED_FIELDS = [
    ('tract_acs_poverty_rate', 'REAL', 'poverty_count / poverty_universe'),
    ('tract_acs_unemployment_rate', 'REAL', 'unemployed / emp_universe'),
    ('tract_acs_pct_white', 'REAL', 'white_pop / race_universe * 100'),
    ('tract_acs_pct_black', 'REAL', 'black_pop / race_universe * 100'),
    ('tract_acs_pct_hispanic', 'REAL', 'hispanic_pop / hispanic_universe * 100'),
    ('tract_acs_pct_bachelors_plus', 'REAL', '(bachelors_count + masters_count + professional_count + doctorate_count) / edu_universe * 100'),
    ('tract_acs_pct_vacant', 'REAL', 'vacant_housing / total_housing * 100'),
    ('tract_acs_pct_owner', 'REAL', 'owner_occupied / (owner_occupied + renter_occupied) * 100'),
]


def load_tract_data():
    """Load ACS tract JSON. Returns dict: geoid → data dict."""
    if not os.path.exists(ACS_DATA):
        print(f"ERROR: ACS tract data not found at {ACS_DATA}")
        print("Run download_tract_acs.py first.")
        sys.exit(1)
    
    with open(ACS_DATA) as f:
        records = json.load(f)
    
    tract_map = {}
    for rec in records:
        geoid = rec.get('geoid', '')
        if geoid:
            tract_map[geoid] = rec
    
    print(f"  Loaded {len(records):,} tract records ({len(tract_map):,} unique GEOIDs)")
    return tract_map


def add_tract_columns(db):
    """Add tract_* columns to churches table if not present."""
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()}
    
    added = 0
    for col_name, col_type, _, _ in TRACT_COLUMNS:
        if col_name not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col_name} {col_type}")
            added += 1
    
    for col_name, col_type, _ in DERIVED_FIELDS:
        if col_name not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col_name} {col_type}")
            added += 1
    
    if added:
        print(f"  Added {added} new tract_* columns")
    else:
        print(f"  All tract_* columns already exist")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Merge ACS tract data into churches')
    parser.add_argument('--dry-run', action='store_true', help='Preview only')
    parser.add_argument('--limit', type=int, default=0, help='Limit churches')
    args = parser.parse_args()
    
    print("=" * 60)
    print("ACS Tract-Level Data Merge")
    print("=" * 60)
    
    # 1. Load tract data
    print("\n[1] Loading ACS tract data...")
    tract_map = load_tract_data()
    
    # 2. Connect to DB
    db = sqlite3.connect(DB_PATH)
    
    # 3. Add columns
    print("\n[2] Adding tract columns...")
    add_tract_columns(db)
    db.commit()
    
    # 4. Get churches that need tract enrichment
    print("\n[3] Finding churches with tract FIPS...")
    query = "SELECT id, tract_fips FROM churches WHERE tract_fips != '' AND tract_fips IS NOT NULL"
    if args.limit:
        query += f" LIMIT {args.limit}"
    
    rows = db.execute(query).fetchall()
    print(f"  Churches with tract FIPS: {len(rows):,}")
    
    # Check how many already have tract data
    already_done = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE tract_acs_total_pop IS NOT NULL
    """).fetchone()[0]
    if already_done:
        print(f"  Already enriched with tract data: {already_done:,}")
    
    if not rows:
        print("\n  No churches with tract FIPS found!")
        print("  Run tract_reverse_geocode.py first.")
        db.close()
        return
    
    # 5. Build lookup and merge
    print("\n[4] Merging tract data...")
    
    update_count = 0
    skip_count = 0
    no_tract = 0
    null_values = {'N/A', 'null', 'None', ''}
    
    # Batch update for efficiency
    for batch_start in range(0, len(rows), 1000):
        batch = rows[batch_start:batch_start + 1000]
        
        for church_id, tract_fips in batch:
            tract_data = tract_map.get(tract_fips)
            if not tract_data:
                no_tract += 1
                continue
            
            # Build SET clause
            set_parts = []
            
            for col_name, _, key, _ in TRACT_COLUMNS:
                val = tract_data.get(key)
                if val is not None and str(val) not in null_values:
                    # Convert numeric strings to numbers
                    try:
                        if '.' in str(val):
                            num_val = float(val)
                        else:
                            num_val = int(val)
                        set_parts.append(f"{col_name}={num_val}")
                    except (ValueError, TypeError):
                        set_parts.append(f"{col_name}='{str(val).replace(chr(39), chr(39)*2)}'")
            
            if set_parts:
                if not args.dry_run:
                    sql = f"UPDATE churches SET {', '.join(set_parts)}, last_updated=datetime('now') WHERE id=?"
                    db.execute(sql, (church_id,))
                update_count += 1
            else:
                skip_count += 1
        
        # Commit every 1000
        if not args.dry_run and (batch_start + 1000) % 10000 == 0:
            db.commit()
            print(f"    Progress: {min(batch_start + 1000, len(rows)):,}/{len(rows):,} churches...")
    
    if not args.dry_run:
        db.commit()
    
    print(f"\n  Merged: {update_count:,} churches")
    print(f"  No tract match: {no_tract:,}")
    print(f"  No tract data to merge: {skip_count:,}")
    
    # 6. Compute derived fields
    if update_count and not args.dry_run:
        print("\n[5] Computing derived fields...")
        
        derived_sqls = {
            'tract_acs_poverty_rate': """
                UPDATE churches SET tract_acs_poverty_rate = 
                    CASE WHEN tract_acs_poverty_universe > 0 
                    THEN ROUND(CAST(tract_acs_poverty_count AS REAL) / tract_acs_poverty_universe, 4)
                    ELSE NULL END
                WHERE tract_acs_poverty_universe > 0
            """,
            'tract_acs_unemployment_rate': """
                UPDATE churches SET tract_acs_unemployment_rate = 
                    CASE WHEN tract_acs_emp_universe > 0 
                    THEN ROUND(CAST(tract_acs_unemployed AS REAL) / tract_acs_emp_universe, 4)
                    ELSE NULL END
                WHERE tract_acs_emp_universe > 0
            """,
            'tract_acs_pct_white': """
                UPDATE churches SET tract_acs_pct_white = 
                    CASE WHEN tract_acs_race_universe > 0 
                    THEN ROUND(CAST(tract_acs_white_pop AS REAL) / tract_acs_race_universe * 100, 1)
                    ELSE NULL END
                WHERE tract_acs_race_universe > 0
            """,
            'tract_acs_pct_black': """
                UPDATE churches SET tract_acs_pct_black = 
                    CASE WHEN tract_acs_race_universe > 0 
                    THEN ROUND(CAST(tract_acs_black_pop AS REAL) / tract_acs_race_universe * 100, 1)
                    ELSE NULL END
                WHERE tract_acs_race_universe > 0
            """,
            'tract_acs_pct_hispanic': """
                UPDATE churches SET tract_acs_pct_hispanic = 
                    CASE WHEN tract_acs_hispanic_universe > 0 
                    THEN ROUND(CAST(tract_acs_hispanic_pop AS REAL) / tract_acs_hispanic_universe * 100, 1)
                    ELSE NULL END
                WHERE tract_acs_hispanic_universe > 0
            """,
            'tract_acs_pct_bachelors_plus': """
                UPDATE churches SET tract_acs_pct_bachelors_plus = 
                    CASE WHEN tract_acs_edu_universe > 0 
                    THEN ROUND(CAST(
                        COALESCE(tract_acs_bachelors_count, 0) + 
                        COALESCE(tract_acs_masters_count, 0) + 
                        COALESCE(tract_acs_professional_count, 0) + 
                        COALESCE(tract_acs_doctorate_count, 0) AS REAL
                    ) / tract_acs_edu_universe * 100, 1)
                    ELSE NULL END
                WHERE tract_acs_edu_universe > 0
            """,
            'tract_acs_pct_vacant': """
                UPDATE churches SET tract_acs_pct_vacant = 
                    CASE WHEN tract_acs_total_housing > 0 
                    THEN ROUND(CAST(tract_acs_vacant_housing AS REAL) / tract_acs_total_housing * 100, 1)
                    ELSE NULL END
                WHERE tract_acs_total_housing > 0
            """,
            'tract_acs_pct_owner': """
                UPDATE churches SET tract_acs_pct_owner = 
                    CASE WHEN (tract_acs_owner_occupied + tract_acs_renter_occupied) > 0 
                    THEN ROUND(CAST(tract_acs_owner_occupied AS REAL) / 
                        (tract_acs_owner_occupied + tract_acs_renter_occupied) * 100, 1)
                    ELSE NULL END
                WHERE (tract_acs_owner_occupied + tract_acs_renter_occupied) > 0
            """,
        }
        
        for field, sql in derived_sqls.items():
            db.execute(sql)
            count = db.execute(
                f"SELECT COUNT(*) FROM churches WHERE {field} IS NOT NULL"
            ).fetchone()[0]
            print(f"  {field:35s} {count:>8,} churches")
        
        db.commit()
    
    # 7. Summary
    print(f"\n[6] Coverage summary:")
    
    # Compare county vs tract coverage
    county_count = db.execute("SELECT COUNT(*) FROM churches WHERE acs_total_pop IS NOT NULL").fetchone()[0]
    tract_count = db.execute("SELECT COUNT(*) FROM churches WHERE tract_acs_total_pop IS NOT NULL").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    
    print(f"  {'':30s} {'County-level':>15s} {'Tract-level':>15s}")
    print(f"  {'Coverage':30s} {county_count/total*100:>14.1f}% {tract_count/total*100:>14.1f}%")
    print(f"  {'Churches':30s} {county_count:>15,d} {tract_count:>15,d}")
    
    if not args.dry_run:
        # Log to provenance
        db.execute("""
            INSERT INTO provenance_log
                (source, script_name, started_at, completed_at,
                 churches_updated, churches_inserted, fields_populated,
                 records_attempted, records_matched, status, notes)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, 'completed', ?)
        """, (
            'acs_tract',
            'merge_tract_data.py',
            datetime.now().isoformat(),
            datetime.now().isoformat(),
            update_count,
            ','.join(c[0] for c in TRACT_COLUMNS + DERIVED_FIELDS),
            len(rows),
            update_count,
            f'Tract-level ACS merge. {tract_count:,} churches enriched at tract resolution.'
        ))
        db.commit()
    
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()

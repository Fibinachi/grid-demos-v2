#!/usr/bin/env python3
"""
Populate county_census_us table by aggregating census_zip_data (zip5-level ACS)
to county level using Census ZCTA -> county crosswalk.

Method:
  1. Download ZCTA5 -> county FIPS crosswalk from Census (free, no API key)
  2. For each ZIP crossing county lines, use county with highest POPPCT
  3. Aggregate zip-level ACS data to county-level with population-weighted averaging
  4. Insert into county_census_us table

Columns populated:
  - COUNT fields (total_pop, white_pop, black_pop, asian_pop, hisp_pop): SUM
  - RATE fields (poverty_rate, pct_bachelors, pct_graduate, etc.): pop-weighted AVG
  - MEDIAN fields (median_hh_income, median_age, etc.): pop-weighted AVG
  - PCT fields (white_pct, black_pct, etc.): computed from SUM totals
  - tract_count_in_county: from tract_lookup_us

Usage:
    python scripts/db_maintenance/populate_county_census_us.py
"""

import csv
import io
import os
import sys
import urllib.request

# ── paths ──────────────────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

from gw_db import connect as get_db

# ── Census ZCTA → county crosswalk ────────────────────────────────────────
ZCTA_COUNTY_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt"

def download_zcta_county():
    """Download ZCTA5 -> county FIPS crosswalk. Returns dict {zcta5: (county_fips, pop_pct)}.
    For ZCTAs crossing county lines, keeps the county with highest POPPCT."""
    print("  Downloading ZCTA->county crosswalk from Census...", end=" ", flush=True)
    try:
        req = urllib.request.Request(ZCTA_COUNTY_URL, headers={"User-Agent": "GRID/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))
        zips = {}
        for row in reader:
            zcta = row["ZCTA5"].strip().zfill(5)
            state_fips = row["STATE"].strip().zfill(2)
            county_fips = row["COUNTY"].strip().zfill(3)
            full_fips = state_fips + county_fips
            pop_pct = float(row.get("ZPOPPCT", "0").strip() or "0")
            if zcta not in zips or pop_pct > zips[zcta][1]:
                zips[zcta] = (full_fips, pop_pct)
        print(f"{len(zips):,} ZCTAs mapped to {len(set(v[0] for v in zips.values())):,} counties")
        return zips
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def main():
    db = get_db()
    cur = db.cursor()

    # ── 1. Get ZIP -> county mapping ─────────────────────────────────────
    print("Step 1: Building ZIP -> county mapping...")
    zcta_map = download_zcta_county()
    if not zcta_map:
        print("ERROR: Could not download crosswalk. Aborting.")
        return 1

    # ── 2. Read all census_zip_data ──────────────────────────────────────
    print("Step 2: Reading census_zip_data...")
    rows = cur.execute("SELECT * FROM census_zip_data WHERE year = 2022").fetchall()
    zip_cols = [col[1] for col in cur.execute("PRAGMA table_info(census_zip_data)").fetchall()]
    print(f"  Found {len(rows):,} zip-level ACS rows (year=2022)")
    print(f"  Columns: {len(zip_cols)}")

    # Build index by zip5
    zip_data = {}
    for r in rows:
        rd = dict(zip(zip_cols, r))
        z5 = str(rd.get("zip5", "") or "").strip().zfill(5)
        zip_data[z5] = rd

    # ── 3. Aggregate to county level ──────────────────────────────────────
    print("Step 3: Aggregating to county level...")
    county_agg = {}  # county_fips -> {col: weighted_sum_or_total}

    # NOTE on census_zip_data quirks:
    #   - owner_pct, renter_pct, vacancy_pct are actually COUNTS not percentages
    #   - pct_bachelors, pct_graduate, pct_some_college are COUNTS not percentages
    #   - median_age is ALL -888888888.0 (sentinel = not available)
    #   - median_home_value, median_gross_rent, mean_commute_min, wfh_pct, gini_index: ALL NULL
    # So several county_census_us columns cannot be populated from this source.
    
    # Field mappings: (county_census_us_col, census_zip_cols, agg_type)
    # agg_type: 'sum' (add counts), 'wavg' (pop-weighted avg), 'pct' (percent from summed totals),
    #           'pci' (per capita income), 'rate' (count/denom * 100)
    FIELD_MAP = [
        ("total_pop",          ("total_pop",),                          "sum"),
        ("median_hh_income",   ("median_hh_income",),                   "wavg"),
        ("poverty_rate",       ("poverty_rate",),                       "wavg"),
        ("unemployment_rate",  ("unemployed_pct",),                     "wavg"),
        # Percentages computed from summed race counts
        ("white_pct",          ("white_pop", "total_pop"),              "pct"),
        ("black_pct",          ("black_pop", "total_pop"),              "pct"),
        ("asian_pct",          ("asian_pop", "total_pop"),              "pct"),
        ("hispanic_pct",       ("hisp_pop", "total_pop"),               "pct"),
        # NOTE: owner_pct in census_zip_data is a copy of total_housing — not useful
        # Income per capita = SUM(mean_hh_income * hh_total) / SUM(total_pop)
        ("income_per_capita",  ("mean_hh_income", "hh_total", "total_pop"), "pci"),
    ]
    
    # Columns NOT populated from census_zip_data (no data available):
    #   bachelors_25_64, graduate_degree — pct_bachelors/graduate are counts, not %
    #   median_age — all sentinel values (-888888888.0)
    #   median_home_value, median_gross_rent — all NULL in source
    #   mean_commute_min, drove_alone_pct, wfh_pct — not available
    #   gini_index — all NULL in source

    skipped_no_fips = 0
    skipped_bad_data = 0
    for z5, data in zip_data.items():
        county_info = zcta_map.get(z5)
        if not county_info:
            skipped_no_fips += 1
            continue
        cfips = county_info[0]

        pop = data.get("total_pop")
        if pop is None or (isinstance(pop, (int, float)) and pop <= 0):
            # Try to get pop from other fields
            pop = data.get("race_total") or data.get("hh_total", 0) * (data.get("avg_hh_size", 0) or 2.5)
            if isinstance(pop, float) and pop <= 0:
                skipped_bad_data += 1
                continue

        if cfips not in county_agg:
            # Initialize accumulators
            acc = {"_count": 0, "_pop_sum": 0.0}
            for ccol, *_ in FIELD_MAP:
                if isinstance(ccol, str):
                    acc[ccol] = 0.0
                    acc[f"{ccol}_w"] = 0.0  # weighted sum
            county_agg[cfips] = acc

        acc = county_agg[cfips]
        acc["_count"] += 1
        acc["_pop_sum"] += float(pop)

        for mapping in FIELD_MAP:
            ccol = mapping[0]
            src = mapping[1]
            agg_type = mapping[2]

            if agg_type == "sum":
                val = data.get(src[0])
                if val is not None:
                    try:
                        fval = float(val)
                        if fval > 0 and fval < 999999999:
                            acc[ccol] += fval
                    except (ValueError, TypeError):
                        pass

            elif agg_type == "wavg":
                val = data.get(src[0])
                if val is not None:
                    try:
                        fval = float(val)
                        # Skip sentinel/null values
                        if fval == -888888888.0 or fval < -1000000 or fval == 0:
                            continue
                        acc[ccol] += fval * float(pop)
                        acc[f"{ccol}_w"] += float(pop)
                    except (ValueError, TypeError):
                        pass

            elif agg_type == "pct":
                num_col, denom_col = src
                num = data.get(num_col)
                denom = data.get(denom_col)
                if num is not None and denom is not None:
                    try:
                        acc[f"{ccol}_num"] = acc.get(f"{ccol}_num", 0.0) + float(num)
                        acc[f"{ccol}_den"] = acc.get(f"{ccol}_den", 0.0) + float(denom)
                    except (ValueError, TypeError):
                        pass

            elif agg_type == "rate":
                # rate = numerator_count / denominator_count * 100
                num_col, denom_col = src
                num = data.get(num_col)
                denom = data.get(denom_col)
                if num is not None and denom is not None:
                    try:
                        acc[f"{ccol}_num"] = acc.get(f"{ccol}_num", 0.0) + float(num)
                        acc[f"{ccol}_den"] = acc.get(f"{ccol}_den", 0.0) + float(denom)
                    except (ValueError, TypeError):
                        pass

            elif agg_type == "pci":
                # Per capita income = (mean_hh_income * hh_total) / total_pop
                mhi_col, hht_col, tpop_col = src
                mhi = data.get(mhi_col) or 0
                hht = data.get(hht_col) or 0
                tpop = data.get(tpop_col) or 0
                try:
                    mhi_f = float(mhi)
                    hht_f = float(hht)
                    tpop_f = float(tpop)
                    if mhi_f > 0 and hht_f > 0 and tpop_f > 0:
                        acc[ccol] += (mhi_f * hht_f)
                        acc[f"{ccol}_w"] += tpop_f
                except (ValueError, TypeError):
                    pass

    print(f"  Aggregated into {len(county_agg):,} counties")
    print(f"  Skipped (no FIPS): {skipped_no_fips:,} ZIPs")
    print(f"  Skipped (bad pop): {skipped_bad_data:,} ZIPs")

    # ── 4. Get tract count per county ────────────────────────────────────
    print("Step 4: Counting tracts per county...")
    tract_count = {}
    try:
        cur.execute("SELECT county_fips, COUNT(*) FROM tract_lookup_us GROUP BY county_fips")
        for row in cur.fetchall():
            tract_count[row[0]] = row[1]
        print(f"  Found tract counts for {len(tract_count):,} counties")
    except Exception as e:
        print(f"  WARNING: Could not count tracts: {e}")

    # ── 5. Write to county_census_us ───────────────────────────────────────────
    print("Step 5: Writing to county_census_us...")
    inserted = 0

    # Get actual columns
    acs_cols = [col[1] for col in cur.execute("PRAGMA table_info(county_census_us)").fetchall()]
    has_tract_count = "tract_count_in_county" in acs_cols
    has_drove_alone = "drove_alone_pct" in acs_cols
    has_source = "source" in acs_cols
    has_updated = "updated_at" in acs_cols

    for cfips, acc in sorted(county_agg.items()):
        if cfips == "" or cfips is None:
            continue

        # Compute final values
        vals = {}
        for mapping in FIELD_MAP:
            ccol = mapping[0]
            agg_type = mapping[2]

            if agg_type == "sum":
                vals[ccol] = acc[ccol] if acc[ccol] else 0
            elif agg_type == "wavg":
                weighted = acc[ccol] or 0
                weight = acc.get(f"{ccol}_w", 0) or 0
                counts = acc["_pop_sum"]
                if weight > 0:
                    vals[ccol] = weighted / weight
                elif counts > 0:
                    vals[ccol] = weighted / counts
                else:
                    vals[ccol] = None
            elif agg_type == "pct":
                num = acc.get(f"{ccol}_num", 0.0) or 0.0
                den = acc.get(f"{ccol}_den", 0.0) or 0.0
                if den and den > 0:
                    vals[ccol] = (num / den) * 100.0
                else:
                    vals[ccol] = None
            elif agg_type == "rate":
                # rate = numerator / denominator * 100
                num = acc.get(f"{ccol}_num", 0.0) or 0.0
                den = acc.get(f"{ccol}_den", 0.0) or 0.0
                if den and den > 0:
                    vals[ccol] = (num / den) * 100.0
                else:
                    vals[ccol] = None
            elif agg_type == "pci":
                total_income = acc[ccol] or 0
                total_pop_w = acc.get(f"{ccol}_w", 0) or 0
                if total_pop_w > 0:
                    vals[ccol] = total_income / total_pop_w
                else:
                    vals[ccol] = None

        # Tract count
        tc = tract_count.get(cfips, 0)
        if has_tract_count:
            vals["tract_count_in_county"] = tc

        # Build INSERT — only columns that have populated values
        insert_cols = ["county_fips"]
        for c in ["total_pop", "median_hh_income", "poverty_rate", "unemployment_rate",
                   "white_pct", "black_pct", "asian_pct", "hispanic_pct",
                   "income_per_capita"]:
            if c in vals and vals[c] is not None and c in acs_cols:
                insert_cols.append(c)
        if has_tract_count:
            insert_cols.append("tract_count_in_county")
        if has_source and "source" in acs_cols:
            insert_cols.append("source")
        if has_updated and "updated_at" in acs_cols:
            insert_cols.append("updated_at")

        # Build VALUES with placeholders for data columns + SQL literals for special ones
        placeholders_list = []
        for c in insert_cols:
            if c == "source":
                placeholders_list.append("'acs_2022_zip_agg'")
            elif c == "updated_at":
                placeholders_list.append("datetime('now')")
            else:
                placeholders_list.append("?")
        placeholders = ",".join(placeholders_list)
        update_cols = ",".join(f"{c}=excluded.{c}" for c in insert_cols if c != "county_fips")
        cols_str = ",".join(insert_cols)

        row_vals = [cfips]
        for c in insert_cols[1:]:
            if c in ("source", "updated_at"):
                continue  # handled as SQL literal above
            v = vals.get(c)
            if isinstance(v, float):
                row_vals.append(round(v, 2))
            else:
                row_vals.append(v)

        cur.execute(f"""
            INSERT INTO county_census_us ({cols_str})
            VALUES ({placeholders})
            ON CONFLICT(county_fips) DO UPDATE SET {update_cols}
        """, row_vals)
        inserted += 1

        if inserted % 500 == 0:
            print(f"  Progress: {inserted:,} counties written")

    db.commit()
    print(f"  county_census_us: {inserted:,} rows written")

    # ── 6. Verify ────────────────────────────────────────────────────────
    print("\n=== Verification ===")
    cnt = cur.execute("SELECT COUNT(*) FROM county_census_us").fetchone()[0]
    print(f"  Total rows: {cnt:,}")
    
    print("\nColumn coverage:")
    for col in ["total_pop", "median_hh_income", "poverty_rate", "unemployment_rate",
                 "white_pct", "black_pct", "asian_pct", "hispanic_pct",
                 "income_per_capita", "tract_count_in_county"]:
        if col in acs_cols:
            nn = cur.execute(f'SELECT COUNT(*) FROM county_census_us WHERE "{col}" IS NOT NULL').fetchone()[0]
            nz = cur.execute(f'SELECT COUNT(*) FROM county_census_us WHERE "{col}" IS NOT NULL AND "{col}" > 0').fetchone()[0]
            print(f'  {col:25s} {nn:>6,} non-null  {nz:>6,} with value')

    # Sample largest counties
    print("\nLargest counties:")
    for row in cur.execute("""
        SELECT county_fips, total_pop, median_hh_income, 
               poverty_rate, white_pct, black_pct
        FROM county_census_us 
        WHERE total_pop > 0
        ORDER BY total_pop DESC
        LIMIT 5
    """).fetchall():
        bp = f'{row[5]:.1f}%' if row[5] is not None else 'N/A'
        print(f'  {row[0]}: pop={row[1]:>10,.0f}  income={row[2]:>8,.0f}  '
              f'poverty={row[3]:>5.1f}%  white={row[4]:>5.1f}%  '
              f'black={bp}')
    
    print("\nSmallest counties:")
    for row in cur.execute("""
        SELECT county_fips, total_pop, median_hh_income
        FROM county_census_us 
        WHERE total_pop > 0
        ORDER BY total_pop ASC
        LIMIT 5
    """).fetchall():
        inc = f'{row[2]:>,.0f}' if row[2] is not None else 'N/A'
        print(f'  {row[0]}: pop={row[1]:>8,.0f}  income={inc}')

    # ── 7. Log provenance ────────────────────────────────────────────────
    print("\nStep 6: Logging provenance...")
    populated_cols = [m[0] for m in FIELD_MAP]
    if has_tract_count:
        populated_cols.append("tract_count_in_county")
    cur.execute("""
        INSERT INTO provenance_log 
            (source, script_name, started_at, completed_at, churches_updated, 
             churches_inserted, fields_populated, records_attempted, status)
        VALUES (?, ?, datetime('now'), datetime('now'), 0, ?, ?, ?, 'completed')
    """, (
        "census_acs_aggregation",
        "populate_county_census_us.py",
        inserted,
        len(county_agg),
        ",".join(populated_cols)
    ))
    db.commit()
    print("  Provenance logged.")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

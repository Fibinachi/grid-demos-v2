#!/usr/bin/env python3
"""
GrantWizard ARDA + Geospatial Enrichment
=========================================
Adds county-level religious demographics + ZIP-to-county linking.

Usage:
    python arda_enrich.py                          # Add FIPS codes + ARDA data to DB
    python arda_enrich.py --drive-time             # Generate drive-time CSV for routing
"""

import csv, os, sqlite3, math, json, urllib.request, time
from collections import defaultdict

DB = r"E:\grid\churches.db"
ARDA_CSV = r"E:\grid\data\arda\arda_county_2020.csv"
ZIP_FIPS = r"E:\grid\data\arda\zip_to_fips.txt"

# ── Step 1: Load ZIP → County FIPS ────────────────────────────────

def load_zip_to_fips():
    """Load Census ZCTA-to-county crosswalk. Returns {zip5: [(fips, weight), ...]}
    Columns: OID_ZCTA5|GEOID_ZCTA5|NAMELSAD|AREALAND|AREAWATER|MTFCC|CLASSFP|FUNCSTAT|
             OID_COUNTY|GEOID_COUNTY|NAMELSAD_COUNTY|AREALAND_COUNTY|AREAWATER_COUNTY|
             MTFCC_COUNTY|CLASSFP_COUNTY|FUNCSTAT_COUNTY|AREALAND_PART|AREAWATER_PART"""
    zips = defaultdict(list)
    with open(ZIP_FIPS, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|")
        for i, row in enumerate(reader):
            if i == 0:  # skip header
                continue
            # GEOID_ZCTA5 is col 1, GEOID_COUNTY is col 9
            zcta = row[1].strip().zfill(5)
            county_fips = row[9].strip()
            if not zcta or not county_fips or zcta == "ZCTA5":
                continue
            try:
                arealand = float(row[16].strip()) if row[16].strip() else 0
                areawater = float(row[17].strip()) if row[17].strip() else 0
                weight = arealand + areawater if arealand > 0 else 1.0
            except:
                weight = 1.0
            fips_code = int(county_fips)
            zips[zcta].append((fips_code, weight))
    return dict(zips)

# ── Step 2: Load ARDA county data ─────────────────────────────────

def load_arda():
    """Load ARDA county religious demographics keyed by FIPS."""
    arda = {}
    with open(ARDA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fips = int(row["fips"])
            arda[fips] = {
                "pop_2020": float(row["pop_2020"] or 0),
                "total_adherents": float(row["total_adherents"] or 0),
                "total_congregations": float(row["total_congregations"] or 0),
                "adherence_rate": float(row["adherence_rate"] or 0),
                "evangelical_adherents": float(row["evangelical_adherents"] or 0),
                "catholic_adherents": float(row["catholic_adherents"] or 0),
                "evangelical_pct": float(row["evangelical_pct"] or 0),
                "catholic_pct": float(row["catholic_pct"] or 0),
            }
    return arda

# ── Step 3: Add to database ───────────────────────────────────────

def add_to_db(zip_lookup, arda_lookup):
    # Connect to a new DB or just output CSV
    db = sqlite3.connect(DB)
    cur = db.cursor()

    # Add columns if missing
    for col in ["fips", "evangelical_pct", "catholic_pct", "adherence_rate", "county_religious_adherence"]:
        cur.execute(f"PRAGMA table_info(churches)")
        cols = [c[1] for c in cur.fetchall()]
        if col not in cols:
            cur.execute(f"ALTER TABLE churches ADD COLUMN {col} TEXT")

    # Update from ZIP codes
    cur.execute("SELECT id, zip FROM churches WHERE fips IS NULL OR fips = ''")
    rows = cur.fetchall()
    updated = 0
    for cid, zip_code in rows:
        if not zip_code:
            continue
        zip5 = str(zip_code).strip().split("-")[0].zfill(5)
        matches = zip_lookup.get(zip5, [])
        if matches:
            # Use highest-weight county
            best = max(matches, key=lambda x: x[1])
            fips = best[0]
            cur.execute("UPDATE churches SET fips=? WHERE id=?", (str(fips), cid))
            updated += 1
        if updated % 10000 == 0 and updated > 0:
            db.commit()

    db.commit()
    print(f"Updated {updated:,} church FIPS codes")

    # Now add ARDA data where we have FIPS
    cur.execute("SELECT id, fips FROM churches WHERE fips IS NOT NULL AND fips != '' AND (evangelical_pct IS NULL OR evangelical_pct = '')")
    rows = cur.fetchall()
    enriched = 0
    for cid, fips_str in rows:
        try:
            fips = int(fips_str)
        except:
            continue
        arda = arda_lookup.get(fips)
        if arda:
            cur.execute("""
                UPDATE churches SET 
                    evangelical_pct=?, catholic_pct=?, adherence_rate=?,
                    county_religious_adherence=?
                WHERE id=?
            """, (
                arda["evangelical_pct"],
                arda["catholic_pct"],
                arda["adherence_rate"],
                json.dumps(arda),
                cid
            ))
            enriched += 1
        if enriched % 5000 == 0 and enriched > 0:
            db.commit()

    db.commit()
    print(f"Enriched {enriched:,} churches with ARDA data")

    # Summary
    cur.execute("SELECT COUNT(*) FROM churches WHERE fips IS NOT NULL AND fips != ''")
    print(f"Churches with FIPS: {cur.fetchone()[0]:,}")
    cur.execute("SELECT COUNT(*) FROM churches WHERE evangelical_pct IS NOT NULL AND evangelical_pct != ''")
    print(f"Churches with ARDA data: {cur.fetchone()[0]:,}")

    db.close()


# ── Step 4: Drive-time CSV export ─────────────────────────────────

def export_for_drive_time():
    """Export churches with lat/lng for drive-time processing."""
    db = sqlite3.connect(DB)
    cur = db.cursor()
    cur.execute("""
        SELECT id, name, city, state, latitude, longitude 
        FROM churches 
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND name != ''
        LIMIT 1000
    """)
    rows = cur.fetchall()
    db.close()

    out = os.path.join(os.path.dirname(DB), "data", "drive_time_targets.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "city", "state", "lat", "lng"])
        w.writerows(rows)
    print(f"Exported {len(rows):,} drive-time targets to {out}")
    print(f"Feed these into: https://map.project-osrm.org/ or Valhalla isochrone API")


# ── Main ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--drive-time", action="store_true")
    args = parser.parse_args()

    if args.drive_time:
        export_for_drive_time()
        return

    print("Loading ZIP-to-FIPS crosswalk...")
    zips = load_zip_to_fips()
    print(f"  {len(zips):,} ZIP codes mapped to counties")

    print("Loading ARDA county data...")
    arda = load_arda()
    print(f"  {len(arda):,} counties loaded")

    print("Adding to database...")
    add_to_db(zips, arda)

    print("\nDone! Cost: $0.00")


if __name__ == "__main__":
    main()

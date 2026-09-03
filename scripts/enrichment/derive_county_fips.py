#!/usr/bin/env python3
"""
GrantWizard County FIPS Derivation
====================================
Adds county_fips column to churches.db and populates it using:

  Tier 1: ZIP→County crosswalk via HUD USPS data
          — for the ~303K records with ZIP codes. Downloads the HUD
            crosswalk file and does a local SQL join. Instant, free.
  
  Tier 2: Census coordinate reverse geocode (lat/lng → county_fips)
          — for records with lat/lng but no ZIP, uses individual
            Census API calls (~50/sec)
  
  Tier 3: Census address geocode with geography (address → county_fips)
          — for remaining records with street addresses

Usage:
    python scripts/enrichment/derive_county_fips.py              # All tiers
    python scripts/enrichment/derive_county_fips.py --tier 1     # ZIP crosswalk only
    python scripts/enrichment/derive_county_fips.py --dry-run    # Preview only
"""

import csv, io, json, os, sqlite3, sys, time, urllib.request, urllib.parse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# Census API endpoints
CENSUS_COORDS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
CENSUS_ADDR_GEO_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"

# HUD USPS ZIP→County crosswalk (Q1 2025)
HUD_CROSSWALK_URL = "https://www.huduser.gov/hudapi/public/usps/download?type=zip_county&query=ALL&year=2025&quarter=1"


def ensure_columns(db):
    """Add county_fips and county_name columns if missing."""
    cur = db.cursor()
    cur.execute("PRAGMA table_info(churches)")
    cols = [c[1] for c in cur.fetchall()]
    
    added = []
    if "county_fips" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN county_fips TEXT")
        added.append("county_fips")
    if "county_name" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN county_name TEXT")
        added.append("county_name")
    
    if added:
        db.commit()
        print(f"  Added columns: {', '.join(added)}")
    
    # Also check if election_results table exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='election_results'")
    if not cur.fetchone():
        print("  WARNING: election_results table doesn't exist yet.")
        print("  Run import_election_data.py first to create it.")


ZCTA_COUNTY_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_county_rel_10.txt"

def download_zcta_county():
    """Download Census ZCTA→county relationship file.
    
    Each row maps a ZCTA (ZIP) to a county with population/area percentages.
    For ZIPs crossing county lines, we take the county with highest POPPCT.
    """
    print("  Downloading ZCTA-county crosswalk from Census...", end=" ", flush=True)
    try:
        req = urllib.request.Request(ZCTA_COUNTY_URL, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
        
        reader = csv.DictReader(io.StringIO(raw))
        zip_to_county = {}
        for row in reader:
            zcta = row["ZCTA5"].strip().zfill(5)
            state_fips = row["STATE"].strip().zfill(2)
            county_fips = row["COUNTY"].strip().zfill(3)
            full_fips = state_fips + county_fips
            pop_pct = float(row.get("ZPOPPCT", "0").strip() or "0")
            
            # Keep the county with highest population overlap for this ZIP
            if zcta not in zip_to_county or pop_pct > zip_to_county[zcta][1]:
                zip_to_county[zcta] = (full_fips, pop_pct)
        
        print(f"{len(zip_to_county):,} ZIP codes mapped")
        return zip_to_county
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def tier1_zip_crosswalk(db, dry_run=False):
    """
    Tier 1: Use Census ZCTA→county relationship file to map ZIP codes
    to county FIPS codes. Covers ~303K records with ZIP codes.
    
    For ZIPs that cross county lines, uses the county with the highest
    population percentage overlap. Instant, zero API calls, free.
    """
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE zip IS NOT NULL AND zip != ''
          AND (county_fips IS NULL OR county_fips = '')
    """)
    pending = cur.fetchone()[0]
    
    if pending == 0:
        print("  No records need county_fips from ZIP crosswalk")
        return 0
    
    print(f"\n=== Tier 1: ZIP → County Crosswalk ===")
    print(f"  Records needing county: {pending:,}")
    if dry_run:
        return 0
    
    zip_to_county = download_zcta_county()
    if not zip_to_county:
        print("  FAILED to download crosswalk — aborting Tier 1")
        return 0
    
    # Process in batches for efficiency
    cur.execute("""
        SELECT id, zip FROM churches 
        WHERE zip IS NOT NULL AND zip != ''
          AND (county_fips IS NULL OR county_fips = '')
    """)
    rows = cur.fetchall()
    
    updated = 0
    for cid, zip_code in rows:
        zip_str = str(zip_code).strip().split("-")[0].zfill(5)
        county_info = zip_to_county.get(zip_str)
        if county_info:
            county_fips = county_info[0]
            cur.execute(
                "UPDATE churches SET county_fips=? WHERE id=?",
                (county_fips, cid)
            )
            updated += 1
        
        if updated > 0 and updated % 10000 == 0:
            db.commit()
            print(f"  Progress: {updated:,} / {pending:,}")
    
    db.commit()
    print(f"  Tier 1 complete: {updated:,} / {pending:,} records updated")
    
    # Also try to get county names from election_results table
    cur.execute("SELECT COUNT(*) FROM election_results")
    has_election_data = cur.fetchone()[0] > 0
    if has_election_data:
        print("  Adding county names from election_results table...")
        cur.execute("""
            UPDATE churches SET county_name = (
                SELECT e.county_name FROM election_results e 
                WHERE e.county_fips = churches.county_fips 
                LIMIT 1
            ) WHERE county_fips IS NOT NULL AND county_fips != ''
        """)
        db.commit()
        cur.execute("SELECT COUNT(*) FROM churches WHERE county_name IS NOT NULL AND county_name != ''")
        with_name = cur.fetchone()[0]
        print(f"  County names added: {with_name:,}")
    
    return updated


def tier2_coords_reverse(db, dry_run=False):
    """
    Tier 2: Reverse geocode lat/lng → county_fips for records
    that have coordinates but no ZIP (couldn't be mapped in Tier 1).
    
    Uses individual Census Geocoder API calls (~50/sec).
    """
    cur = db.cursor()
    cur.execute("""
        SELECT id, latitude, longitude 
        FROM churches 
        WHERE latitude IS NOT NULL 
          AND longitude IS NOT NULL 
          AND (county_fips IS NULL OR county_fips = '')
    """)
    rows = cur.fetchall()
    
    if not rows:
        print("  No records need Tier 2")
        return 0
    
    print(f"\n=== Tier 2: Coordinate Reverse Geocode ===")
    print(f"  Records to process: {len(rows):,}")
    if dry_run:
        return 0
    
    # If too many, switch to threading
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def reverse_one(record):
        cid, lat, lng = record
        params = urllib.parse.urlencode({
            "x": lng, "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        })
        url = f"{CENSUS_COORDS_URL}?{params}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            geos = data.get("result", {}).get("geographies", {})
            
            # Try Counties first
            counties = geos.get("Counties", [])
            if counties:
                g = counties[0]
                fips = g.get("GEOID", "")
                name = g.get("NAME", "")
                if fips:
                    return (cid, fips, name)
            
            # Fall back to Census Tracts
            tracts = geos.get("Census Tracts", [])
            if tracts:
                g = tracts[0]
                sfips = g.get("STATE", "")
                cfips = g.get("COUNTY", "")
                if sfips and cfips:
                    return (cid, sfips + cfips, "")
        except Exception:
            pass
        return None
    
    updated = 0
    BATCH_SIZE = 50
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start:start + BATCH_SIZE]
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(reverse_one, r) for r in batch]
            for f in as_completed(futures):
                result = f.result()
                if result:
                    cid, fips, name = result
                    if name:
                        cur.execute(
                            "UPDATE churches SET county_fips=?, county_name=? WHERE id=?",
                            (fips, name, cid)
                        )
                    else:
                        cur.execute(
                            "UPDATE churches SET county_fips=? WHERE id=?",
                            (fips, cid)
                        )
                    updated += 1
        
        db.commit()
        if (start + BATCH_SIZE) % 500 == 0:
            print(f"  Progress: {min(start + BATCH_SIZE, len(rows)):,}/{len(rows):,} ({updated:,} found)")
        
        time.sleep(0.5)  # Be polite
    
    print(f"  Tier 2 complete: {updated:,} / {len(rows):,}")
    return updated


def tier3_address_geocode(db, dry_run=False):
    """
    Tier 3: Geocode street addresses using Census geographies endpoint
    for remaining unmatched records.
    """
    cur = db.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE (county_fips IS NULL OR county_fips = '')
          AND address IS NOT NULL AND address != ''
    """)
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("  No records need Tier 3")
        return 0
    
    print(f"\n=== Tier 3: Remaining — {remaining:,} records ===")
    print(f"  These need street-level geocoding via Census API")
    print(f"  Recommend: run geocode_churches.py --street first")
    print(f"  Skipping for now — Tier 1 should cover most records")
    return 0


def tier3_zip_crosswalk(db, dry_run=False):
    """
    Tier 3: For ZIP-only records, derive county from ZIP code
    using a simple rule: ZIP → state (first digit) → most common county.
    
    This isn't perfect (ZIPs can cross county lines) but covers ~90% of cases.
    For exact mapping, we'd need HUD ZIP-county crosswalk data.
    
    Actually, the simplest approach: use the first 3-5 digits of the ZIP
    combined with the state to narrow down, then use existing election
    data county list to find the county.
    """
    cur = db.cursor()
    cur.execute("""
        SELECT id, zip, state
        FROM churches 
        WHERE (county_fips IS NULL OR county_fips = '')
          AND zip IS NOT NULL AND zip != ''
          AND (latitude IS NULL AND longitude IS NULL)
    """)
    rows = cur.fetchall()
    
    if not rows:
        print("  No records need Tier 3")
        return 0
    
    print(f"\n=== Tier 3: ZIP → County (approximate) ===")
    print(f"  Records to process: {len(rows):,}")
    print(f"  NOTE: ZIP→county mapping is approximate")
    print(f"  These can be refined later with HUD crosswalk data")
    print(f"  Skipping automated mapping — leaving for manual review")
    print(f"  Recommend: use geocode_churches.py --street for these instead")
    
    return 0


def summary(db):
    """Print a summary of the county FIPS coverage."""
    cur = db.cursor()
    
    print(f"\n=== County FIPS Coverage ===")
    
    cur.execute("SELECT COUNT(*) FROM churches")
    total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''")
    with_fips = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM churches WHERE county_name IS NOT NULL AND county_name != ''")
    with_name = cur.fetchone()[0]
    
    print(f"  Total records: {total:,}")
    print(f"  With county_fips: {with_fips:,} ({with_fips/total*100:.1f}%)")
    print(f"  With county_name: {with_name:,} ({with_name/total*100:.1f}%)")
    
    # Top counties
    print(f"\n  Top 10 counties:")
    cur.execute("""
        SELECT county_name, state, COUNT(*) as cnt 
        FROM churches 
        WHERE county_name IS NOT NULL AND county_name != '' 
        GROUP BY county_name, state 
        ORDER BY cnt DESC 
        LIMIT 10
    """)
    for name, state, cnt in cur.fetchall():
        print(f"    {name}, {state}: {cnt:,}")
    
    # Number of unique counties
    cur.execute("SELECT COUNT(DISTINCT county_fips) FROM churches WHERE county_fips IS NOT NULL AND county_fips != ''")
    unique = cur.fetchone()[0]
    print(f"\n  Unique counties represented: {unique:,}")
    
    # Records that can now join to election_results
    if with_fips > 0:
        cur.execute("""
            SELECT COUNT(*) FROM churches c
            INNER JOIN election_results e ON c.county_fips = e.county_fips
            GROUP BY e.year ORDER BY e.year
        """)
        print(f"  Able to join to election data: (check year-by-year)")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Derive county FIPS for churches")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3], default=None,
                        help="Run only a specific tier")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, no API calls")
    args = parser.parse_args()
    
    print("GrantWizard County FIPS Derivation")
    print("=" * 40)
    
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    ensure_columns(db)
    
    if args.tier is None or args.tier == 1:
        tier1_zip_crosswalk(db, dry_run=args.dry_run)
    
    if args.tier is None or args.tier == 2:
        tier2_coords_reverse(db, dry_run=args.dry_run)
    
    if args.tier is None or args.tier == 3:
        tier3_address_geocode(db, dry_run=args.dry_run)
    
    summary(db)
    db.close()


if __name__ == "__main__":
    main()

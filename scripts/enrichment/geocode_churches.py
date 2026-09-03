#!/usr/bin/env python3
"""
GrantWizard Geocoder
====================
Adds lat/lng to churches.db using a two-tier approach:
  Tier 1: ZIP code centroid from Census ZCTA (free, instant, 33K ZIPs)
  Tier 2: Street-level via Census Geocoder API (free, for high-value targets)

Usage:
    python geocode_churches.py                        # ZIP centroid for all
    python geocode_churches.py --street               # + Census street-level for websites
    python geocode_churches.py --street-only 100      # First 100 with websites

Total cost: $0.00
"""

import sqlite3, csv, os, json, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

DB_PATH = r"E:\grid\churches.db"
ZCTA_PATH = r"E:\grid\data\Gaz_zcta_national.txt"

# ── Tier 1: Load ZIP → lat/lng from Census ZCTA ──────────────────

def load_zcta():
    """Load ZIP Code Tabulation Area centroids into dict."""
    zips = {}
    with open(ZCTA_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        # Strip trailing whitespace from column names
        reader.fieldnames = [n.strip() for n in reader.fieldnames]
        for row in reader:
            zip_code = row["GEOID"].strip().zfill(5)
            try:
                lat = float(row["INTPTLAT"].strip())
                lng = float(row["INTPTLONG"].strip())
                zips[zip_code] = (lat, lng)
            except ValueError:
                continue
    return zips

def geocode_by_zip(zip_lookup, zip_code):
    """Look up lat/lng from ZIP code. Handles ZIP+4 format."""
    if not zip_code:
        return (None, None)
    zip_str = str(zip_code).strip().split("-")[0].zfill(5)
    return zip_lookup.get(zip_str, (None, None))


# ── Tier 2: Census Geocoder (street-level, free) ─────────────────

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

def geocode_street(address, city, state, zip_code):
    """Geocode a single address via Census Geocoder."""
    addr = f"{address}, {city}, {state} {zip_code}"
    params = urllib.parse.urlencode({
        "address": addr,
        "benchmark": "2020",
        "format": "json",
    })
    url = f"{CENSUS_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            matches = data.get("result", {}).get("addressMatches", [])
            if matches:
                c = matches[0]["coordinates"]
                return float(c["y"]), float(c["x"])
    except:
        pass
    return None, None


# ── Main ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Geocode churches")
    parser.add_argument("--street", action="store_true", help="Also do street-level Census geocoding for churches with addresses")
    parser.add_argument("--street-only", type=int, default=None, help="Street-level only for first N churches with websites")
    args = parser.parse_args()

    print("Loading ZIP code centroids...")
    zip_lookup = load_zcta()
    print(f"  Loaded {len(zip_lookup):,} ZIP codes")

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    # Check if lat/lng columns exist
    cur.execute("PRAGMA table_info(churches)")
    cols = [c[1] for c in cur.fetchall()]
    if "latitude" not in cols:
        cur.execute("ALTER TABLE churches ADD COLUMN latitude REAL")
        cur.execute("ALTER TABLE churches ADD COLUMN longitude REAL")
        cur.execute("ALTER TABLE churches ADD COLUMN geocode_source TEXT")
        db.commit()
        print("  Added latitude, longitude, geocode_source columns")

    # Count ungeocoded
    cur.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL")
    pending = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM churches")
    total = cur.fetchone()[0]
    print(f"  {pending:,} / {total:,} churches need geocoding")

    if pending == 0:
        print("  All already geocoded!")
        db.close()
        return

    # Tier 1: ZIP centroid for all ungeocoded
    cur.execute("SELECT id, zip FROM churches WHERE latitude IS NULL")
    rows = cur.fetchall()
    updated = 0
    for cid, zip_code in rows:
        lat, lng = geocode_by_zip(zip_lookup, zip_code)
        if lat and lng:
            cur.execute("UPDATE churches SET latitude=?, longitude=?, geocode_source='zip_centroid' WHERE id=?", (lat, lng, cid))
            updated += 1
        if updated % 10000 == 0:
            db.commit()
            print(f"  ZIP geocoded: {updated:,} / {len(rows):,}")

    db.commit()
    print(f"  ZIP centroid geocoding complete: {updated:,} churches")

    # Tier 2: Street-level Census for high-value targets
    if args.street or args.street_only is not None:
        if args.street_only:
            limit = args.street_only
        else:
            # Churches with websites that still only have ZIP centroid
            limit = -1

        q = "SELECT id, address, city, state, zip FROM churches WHERE geocode_source='zip_centroid' AND website IS NOT NULL AND website != ''"
        if limit > 0:
            q += f" LIMIT {limit}"
        cur.execute(q)
        street_rows = cur.fetchall()
        print(f"  Street-level geocoding for {len(street_rows):,} churches with websites...")

        def do_one(row):
            cid, addr, city, state, zip_code = row
            if not addr or not city or not state:
                return None
            lat, lng = geocode_street(addr, city, state, zip_code)
            if lat and lng:
                return (lat, lng, cid)
            return None

        upgraded = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(do_one, r) for r in street_rows]
            for i, f in enumerate(as_completed(futures)):
                result = f.result()
                if result:
                    lat, lng, cid = result
                    cur.execute("UPDATE churches SET latitude=?, longitude=?, geocode_source='census_street' WHERE id=?", (lat, lng, cid))
                    upgraded += 1
                if i > 0 and i % 100 == 0:
                    db.commit()
                    print(f"    Street geocoded: {upgraded:,} / {i:,} ({(i/len(street_rows)*100):.0f}%)")
                time.sleep(0.5)  # Rate limit: 2/sec

        db.commit()
        print(f"  Street-level upgrades: {upgraded:,} / {len(street_rows):,}")

    # Summary
    cur.execute("SELECT geocode_source, COUNT(*) FROM churches WHERE latitude IS NOT NULL GROUP BY geocode_source")
    print("\n=== Geocoding Summary ===")
    for src, cnt in cur.fetchall():
        print(f"  {src}: {cnt:,}")
    cur.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL")
    print(f"  Ungeocoded: {cur.fetchone()[0]:,}")

    db.close()
    print("\nDone! Cost: $0.00")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GrantWizard — Address Lookup via Nominatim (OpenStreetMap)
Free API, rate-limited to 1 req/sec.

Modes:
  forward  (default) — name+city+state -> lat/lng + street address
  reverse            — lat/lng -> street address (for churches with coords but no addr)

Usage:
  python lookup_addresses_nominatim.py --mode reverse --country US
  python lookup_addresses_nominatim.py --mode reverse --country US --limit 100
  python lookup_addresses_nominatim.py --mode forward --country US
"""
import json, os, sys, time, urllib.request, urllib.parse

# Resolve project root for imports
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
from gw_db import connect

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
UA = "GrantWizard/1.0 (grid-address-lookup; contact@gridproject.org)"

def progress_bar(current, total, bar_width=40):
    """Simple ASCII progress bar."""
    if total == 0:
        return ""
    pct = current / total
    filled = int(bar_width * pct)
    bar = "█" * filled + "░" * (bar_width - filled)
    return f"|{bar}| {pct*100:5.1f}%"

def extract_street_address(data):
    """Extract a street address from Nominatim response address details."""
    addr = data.get("address", {})
    housenum = addr.get("house_number", "")
    road = addr.get("road", "") or addr.get("pedestrian", "") or addr.get("street", "")
    if housenum and road:
        return f"{housenum} {road}"
    return road or ""

def geocode_forward(name, city, state_s):
    """Forward geocode: name+city+state -> lat/lng + address."""
    query = f"{name}, {city}, {state_s}"
    params = urllib.parse.urlencode({
        "q": query, "format": "json", "limit": 1, "addressdetails": 1
    })
    url = f"{NOMINATIM_URL}/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    r = data[0]
    lat = float(r["lat"])
    lng = float(r["lon"])
    street = extract_street_address(r)
    return lat, lng, street

def geocode_reverse(lat, lng):
    """Reverse geocode: lat/lng -> street address. Returns (street, city, zip, display_name) or None."""
    params = urllib.parse.urlencode({
        "lat": lat, "lon": lng, "format": "json", "addressdetails": 1
    })
    url = f"{NOMINATIM_URL}/reverse?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data:
        return None
    street = extract_street_address(data)
    addr = data.get("address", {})
    city = addr.get("city", "") or addr.get("town", "") or addr.get("village", "") or addr.get("hamlet", "")
    zipcode = addr.get("postcode", "")
    display_name = data.get("display_name", "")
    return street, city, zipcode, display_name

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["forward", "reverse"], default="forward",
                        help="forward: name+city+state->lat/lng | reverse: lat/lng->address")
    parser.add_argument("--country", type=str, default="",
                        help="Country code filter (e.g., US). Empty = all countries.")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit records processed (0=all)")
    parser.add_argument("--resume", type=int, default=0,
                        help="Resume from this church ID (skip earlier)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay between requests in seconds (default 1.0 for Nominatim ToS)")
    parser.add_argument("--commit-every", type=int, default=500,
                        help="Commit to DB every N records")
    args = parser.parse_args()

    mode_name = "Forward Geocode" if args.mode == "forward" else "Reverse Geocode"
    country_info = f" ({args.country})" if args.country else " (all countries)"
    print(f"GrantWizard — Nominatim {mode_name}{country_info}")
    print(f"Delay: {args.delay}s | Commit every: {args.commit_every}")

    db = connect()
    db.execute("PRAGMA journal_mode=WAL")
    cur = db.cursor()

    if args.mode == "forward":
        # Forward: churches with name+city+state but no lat/lng
        where = ["(address IS NULL OR address = '')",
                 "name IS NOT NULL AND name != ''",
                 "city IS NOT NULL AND city != ''",
                 "state IS NOT NULL AND state != ''"]
        if args.country:
            where.append(f"country = '{args.country}'")
        if args.resume:
            where.append(f"id >= {args.resume}")
        cur.execute(f"""
            SELECT id, name, city, state FROM churches
            WHERE {' AND '.join(where)}
            ORDER BY id
        """)
    else:
        # Reverse: churches with lat/lng but no address
        where = ["(address IS NULL OR address = '')",
                 "latitude IS NOT NULL AND longitude IS NOT NULL",
                 "latitude != 0"]
        if args.country:
            where.append(f"country = '{args.country}'")
        if args.resume:
            where.append(f"id >= {args.resume}")
        cur.execute(f"""
            SELECT id, latitude, longitude, city, state, name FROM churches
            WHERE {' AND '.join(where)}
            ORDER BY id
        """)

    records = cur.fetchall()
    if args.limit > 0:
        records = records[:args.limit]

    print(f"Records to process: {len(records):,} (~{len(records)*args.delay/3600:.1f}h at {args.delay}s delay)")
    if not records:
        print("Nothing to do!")
        db.close()
        return

    upgraded = 0
    addr_found = 0
    error_count = 0
    start = time.time()
    last_commit = 0

    for i, rec in enumerate(records):
        this_id = rec[0]
        try:
            if args.mode == "forward":
                cid, name, city, state_s = rec
                result = geocode_forward(name, city, state_s)
                if result:
                    lat, lng, street = result
                    if street:
                        db.execute(
                            "UPDATE churches SET latitude=?, longitude=?, address=?, address_source='nominatim', geocode_source='nominatim_name' WHERE id=?",
                            (lat, lng, street, cid))
                        addr_found += 1
                        print(f"  ✅ {cid} | {name[:40]} | {city}, {state_s} | addr found ({street[:50]})")
                    else:
                        db.execute(
                            "UPDATE churches SET latitude=?, longitude=?, geocode_source='nominatim_name' WHERE id=?",
                            (lat, lng, cid))
                        print(f"  📍 {cid} | {name[:40]} | {city}, {state_s} | coords only (no street)")
                    upgraded += 1
                else:
                    print(f"  ❌ {cid} | {name[:40]} | {city}, {state_s} | no match")
            else:
                cid, lat, lng, city, state_s, name = rec
                result = geocode_reverse(lat, lng)
                if result:
                    street, r_city, r_zip, display = result
                    if street:
                        db.execute(
                            "UPDATE churches SET address=?, address_source='nominatim_reverse' WHERE id=?",
                            (street, cid))
                        addr_found += 1
                        print(f"  ✅ {cid} | {str(name)[:35] if name else '?'} | ({lat:.4f},{lng:.4f}) | {street[:50]}")
                    else:
                        print(f"  📍 {cid} | {str(name)[:35] if name else '?'} | ({lat:.4f},{lng:.4f}) | reverse ok, no street")
                    upgraded += 1
                else:
                    print(f"  ❌ {cid} | {str(name)[:35] if name else '?'} | ({lat:.4f},{lng:.4f}) | no reverse match")
        except Exception as e:
            error_count += 1
            err_msg = str(e)[:80]
            print(f"  ⚠ {this_id} | ERROR: {err_msg}")
            if error_count > 50:
                print("  Too many errors, aborting!")
                db.commit()
                db.close()
                sys.exit(1)

        # Progress
        n = i + 1
        if n % 100 == 0 or n == len(records):
            elapsed = time.time() - start
            rate = n / elapsed if elapsed > 0 else 0
            eta = (len(records) - n) / rate if rate > 0 else 0
            bar = progress_bar(n, len(records))
            print(f"  [{n:>7,}/{len(records):,}] {bar} {rate:.2f}/s | {upgraded:,} matched ({addr_found:,} w/ addr) | {error_count} errs | ETA {eta/3600:.1f}h | last_id={this_id}")

        # Commit periodically
        if n - last_commit >= args.commit_every:
            db.commit()
            last_commit = n

        time.sleep(args.delay)

    db.commit()
    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"Done! {upgraded:,}/{len(records):,} matched ({addr_found:,} with address) in {elapsed/3600:.1f}h")
    print(f"Errors: {error_count}")
    if records:
        print(f"Last ID processed: {records[-1][0]}")
    db.close()

if __name__ == "__main__":
    main()

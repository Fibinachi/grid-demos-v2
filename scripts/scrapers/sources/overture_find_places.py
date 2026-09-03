#!/usr/bin/env python3
"""
Overture Place Finder — Chabad, JW, LDS
=========================================
Searches the US using Overture Maps, tile-by-tile. Saves results
incrementally with checkpoint/resume.

Usage:
    # Run all US states (may take hours — run overnight)
    python scripts/scrapers/sources/overture_find_places.py

    # Test on SC only
    python scripts/scrapers/sources/overture_find_places.py --limit-states SC

    # Import results into DB
    python scripts/scrapers/sources/overture_find_places.py --import-db

Output: data/overture_places.jsonl
"""

import json, os, sys, time, re
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR)))
OUTPUT_PATH = os.path.join(PROJECT_DIR, "data", "overture_places.jsonl")
CHECKPOINT_PATH = os.path.join(PROJECT_DIR, "data", "overture_tiles_done.json")
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

# Search terms (name keywords -> group info)
SEARCH_RULES = [
    (re.compile(r'chabad|lubavitch', re.I), 'chabad', 'Jewish (Chabad)', 'jewish'),
    (re.compile(r'kingdom hall|jehovah', re.I), 'jw', "Jehovah's Witness", 'jehovahs_witness'),
    (re.compile(r'church of jesus christ|lds mormon|latter.day|stake center|meetinghouse|lds chapel|mormon church', re.I),
     'lds', 'LDS / Mormon', 'lds'),
]

# State bounding boxes
STATE_BBOXES = {
    "AL": [-88.5, 30.1, -84.9, 35.0], "AZ": [-115.0, 31.3, -109.0, 37.0],
    "AR": [-94.6, 33.0, -89.6, 36.5], "CA": [-124.5, 32.5, -114.1, 42.0],
    "CO": [-109.1, 36.9, -102.0, 41.0], "CT": [-73.7, 40.9, -71.8, 42.1],
    "DE": [-75.8, 38.4, -75.0, 39.9], "DC": [-77.2, 38.8, -76.9, 39.0],
    "FL": [-87.6, 24.4, -80.0, 31.0], "GA": [-85.6, 30.3, -80.8, 35.0],
    "HI": [-160.3, 18.9, -154.8, 22.3], "ID": [-117.3, 41.9, -111.0, 49.0],
    "IL": [-91.5, 36.9, -87.4, 42.5], "IN": [-88.1, 37.7, -84.8, 41.8],
    "IA": [-96.6, 40.3, -90.1, 43.5], "KS": [-102.1, 36.9, -94.6, 40.0],
    "KY": [-89.6, 36.5, -81.9, 39.2], "LA": [-94.1, 28.8, -88.8, 33.1],
    "ME": [-71.1, 42.9, -66.9, 47.5], "MD": [-79.5, 37.8, -75.0, 39.8],
    "MA": [-73.5, 41.2, -69.9, 42.9], "MI": [-90.4, 41.7, -82.1, 47.5],
    "MN": [-97.3, 43.4, -89.4, 49.4], "MS": [-91.7, 30.0, -88.0, 35.0],
    "MO": [-95.8, 35.9, -89.0, 40.6], "MT": [-116.1, 44.3, -104.0, 49.0],
    "NE": [-104.1, 39.9, -95.3, 43.0], "NV": [-120.1, 35.0, -114.0, 42.0],
    "NH": [-72.6, 42.6, -70.6, 45.4], "NJ": [-75.6, 38.8, -73.9, 41.4],
    "NM": [-109.1, 31.3, -103.0, 37.0], "NY": [-80.0, 40.4, -71.8, 45.0],
    "NC": [-84.3, 33.8, -75.4, 36.6], "ND": [-104.1, 45.9, -96.5, 49.0],
    "OH": [-84.8, 38.4, -80.5, 42.0], "OK": [-103.0, 33.6, -94.4, 37.0],
    "OR": [-124.6, 41.9, -116.4, 46.3], "PA": [-80.5, 39.7, -74.7, 42.3],
    "RI": [-71.9, 41.1, -71.1, 42.0], "SC": [-83.4, 32.0, -78.5, 35.2],
    "SD": [-104.1, 42.4, -96.4, 45.9], "TN": [-90.3, 34.9, -81.6, 36.7],
    "TX": [-106.6, 25.8, -93.5, 36.5], "UT": [-114.1, 36.9, -109.0, 42.0],
    "VT": [-73.5, 42.7, -71.5, 45.0], "VA": [-83.7, 36.5, -75.2, 39.5],
    "WA": [-124.8, 45.5, -116.9, 49.0], "WV": [-82.7, 37.2, -77.7, 40.6],
    "WI": [-92.9, 42.5, -86.8, 47.0], "WY": [-111.1, 40.9, -104.0, 45.0],
}


def generate_tiles(bbox, tile_deg=1.5):
    """Split a bounding box into tiles of tile_deg degrees."""
    west, south, east, north = bbox
    tiles = []
    lat = south
    while lat < north:
        lng = west
        while lng < east:
            tiles.append([lng, lat, min(lng + tile_deg, east), min(lat + tile_deg, north)])
            lng += tile_deg
        lat += tile_deg
    return tiles


def search_place_names(names_dict):
    """Check if a names dict contains any of our search terms."""
    if not isinstance(names_dict, dict):
        text = str(names_dict).lower()
    else:
        text = " ".join(str(v) for v in names_dict.values()).lower()
    for pattern, group, denom, family in SEARCH_RULES:
        if pattern.search(text):
            return group, denom, family
    return None


def extract_name(names_dict):
    if not isinstance(names_dict, dict):
        return str(names_dict) if names_dict else ""
    return names_dict.get("primary") or names_dict.get("common") or names_dict.get("official") or ""


def extract_addr(addresses):
    """Extract address components from Overture addresses ndarray."""
    freeform, locality, region, postcode = "", "", "", ""
    if addresses is not None and hasattr(addresses, "__len__") and len(addresses) > 0:
        first = addresses[0]
        if isinstance(first, dict):
            freeform = first.get("freeform", "") or ""
            locality = first.get("locality", "") or ""
            region = first.get("region", "") or ""
            postcode = first.get("postcode", "") or ""
    return freeform, locality, region, postcode


def query_tile(tile):
    """Query Overture for a single tile and return matching places."""
    import overturemaps
    reader = overturemaps.record_batch_reader(overture_type="place", bbox=tile)
    df = reader.read_pandas()
    if len(df) == 0:
        return []

    results = []
    seen = set()

    for _, row in df.iterrows():
        names = row.get("names", {})
        name = extract_name(names)
        if not name:
            continue

        match = search_place_names(names)
        if not match:
            continue

        group, denom, family = match
        freeform, locality, region, postcode = extract_addr(row.get("addresses"))

        # Get coords from bbox (xmin=x=lng, ymin=y=lat)
        bbox = row.get("bbox")
        lat, lng = None, None
        if isinstance(bbox, dict):
            lng = bbox.get("xmin")
            lat = bbox.get("ymin")

        dk = f"{name.lower()[:30]}|{freeform[:20]}|{locality[:15]}"
        if dk in seen:
            continue
        seen.add(dk)

        results.append({
            "name": name.strip(), "address": freeform.strip(),
            "city": locality.strip(), "state": region.strip(),
            "zip": postcode.strip(), "lat": lat, "lng": lng,
            "group": group, "denomination": denom, "family": family,
            "source": "overture",
        })

    return results


def load_checkpoint():
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH) as f:
            return set(json.load(f))
    return set()


def save_checkpoint(done_tiles):
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(sorted(done_tiles), f)


def import_to_db(results):
    import sqlite3
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=5000")
    new_count, match_count = 0, 0
    for r in results:
        cur = db.execute("SELECT id FROM churches WHERE name=? AND state=? LIMIT 1", (r["name"], r["state"]))
        exist = cur.fetchone()
        if exist:
            db.execute("UPDATE churches SET address=COALESCE(NULLIF(?,''),address),city=COALESCE(NULLIF(?,''),city),zip=COALESCE(NULLIF(?,''),zip),latitude=COALESCE(?,latitude),longitude=COALESCE(?,longitude),denomination=COALESCE(NULLIF(?,''),denomination),family=COALESCE(NULLIF(?,''),family) WHERE id=?",
                       (r["address"], r["city"], r["zip"], r["lat"], r["lng"], r["denomination"], r["family"], exist[0]))
            match_count += 1
        else:
            db.execute("INSERT INTO churches (name,address,city,state,zip,latitude,longitude,denomination,family,source) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (r["name"], r["address"], r["city"], r["state"], r["zip"], r["lat"], r["lng"], r["denomination"], r["family"], r["source"]))
            new_count += 1
    db.commit()
    db.close()
    return new_count, match_count


def run():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-states", type=str, default=None)
    parser.add_argument("--import-db", action="store_true")
    parser.add_argument("--tile-deg", type=float, default=1.5, help="Tile size in degrees")
    args = parser.parse_args()

    # Build tile list
    if args.limit_states:
        states = {s.upper(): STATE_BBOXES[s.upper()] for s in args.limit_states.split(",") if s.upper() in STATE_BBOXES}
    else:
        states = STATE_BBOXES

    all_tiles = []
    tile_to_state = {}
    for st, bbox in states.items():
        tiles = generate_tiles(bbox, args.tile_deg)
        for t in tiles:
            key = f"{st}_{t[0]:.1f}_{t[1]:.1f}"
            all_tiles.append((key, t, st))
            tile_to_state[key] = st

    done_tiles = load_checkpoint()
    total = len(all_tiles)
    remaining = [t for t in all_tiles if t[0] not in done_tiles]
    print(f"Total tiles: {total} | Already done: {len(done_tiles)} | Remaining: {len(remaining)}")

    if not remaining:
        print("All tiles done!")
        return

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    all_results = []
    start = time.time()

    for idx, (tile_key, bbox, state) in enumerate(remaining):
        print(f"  [{idx+1}/{len(remaining)}] {tile_key}...", end=" ", flush=True)
        t0 = time.time()
        try:
            results = query_tile(bbox)
            elapsed = time.time() - t0
            print(f"{len(results):,} matches in {elapsed:.0f}s")

            if results:
                with open(OUTPUT_PATH, "a", encoding="utf-8") as f:
                    for r in results:
                        f.write(json.dumps(r, default=str) + "\n")
                all_results.extend(results)
        except Exception as e:
            print(f"ERROR: {e}")
            elapsed = time.time() - t0
            print(f"  (took {elapsed:.0f}s before error)")

        done_tiles.add(tile_key)
        if (idx + 1) % 10 == 0:
            save_checkpoint(done_tiles)
            total_elapsed = time.time() - start
            print(f"  [{idx+1}/{len(remaining)} checkpoint] {len(all_results):,} total | {total_elapsed:.0f}s elapsed")

    save_checkpoint(done_tiles)
    total_elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"Done! {len(all_results):,} total in {total_elapsed:.0f}s")
    for g, cnt in Counter(r["group"] for r in all_results).most_common():
        print(f"  {g:10s}: {cnt:>5}")

    if args.import_db and all_results:
        print("\nImporting to churches.db...")
        n, m = import_to_db(all_results)
        print(f"  New: {n:,}  Updated: {m:,}")

    print("Done!")


if __name__ == "__main__":
    run()

#!/usr/bin/env python3
"""
Overture Maps — ALL religious places scraper.
Queries Overture's open Places dataset by state for every religious category.
Outputs CSV with name, category, subcategory, address, city, state, zip, lat, lon, website, phone.
"""
import csv, os, sys, time
from datetime import datetime

import overturemaps

STATE_BBOX = {
    "AL": [-88.5,30.1,-84.9,35.0], "AZ": [-115.0,31.3,-109.0,37.0], "AR": [-94.6,33.0,-89.6,36.5],
    "CA": [-124.5,32.5,-114.1,42.0], "CO": [-109.1,37.0,-102.0,41.0], "CT": [-73.7,40.9,-71.8,42.1],
    "DE": [-75.8,38.4,-75.0,39.9], "FL": [-87.8,24.4,-80.0,31.0], "GA": [-85.6,30.4,-80.8,35.0],
    "ID": [-117.3,42.0,-111.0,49.0], "IL": [-91.6,36.9,-87.4,42.5], "IN": [-88.2,37.8,-84.8,41.8],
    "IA": [-96.7,40.3,-90.1,43.5], "KS": [-102.1,36.9,-94.6,40.0], "KY": [-89.6,36.5,-81.9,39.1],
    "LA": [-94.1,28.9,-88.8,33.0], "ME": [-71.1,43.0,-66.9,47.5], "MD": [-79.5,37.9,-75.0,39.7],
    "MA": [-73.5,41.2,-69.9,42.9], "MI": [-90.5,41.7,-82.1,48.3], "MN": [-97.3,43.5,-89.5,49.4],
    "MS": [-91.7,30.0,-88.1,35.0], "MO": [-95.8,36.0,-89.1,40.6], "MT": [-116.1,44.3,-104.0,49.0],
    "NE": [-104.1,40.0,-95.3,43.0], "NV": [-120.1,35.0,-114.0,42.0], "NH": [-72.6,42.7,-70.6,45.3],
    "NJ": [-75.6,38.9,-73.9,41.4], "NM": [-109.1,31.3,-103.0,37.0], "NY": [-80.0,40.5,-71.8,45.0],
    "NC": [-84.4,34.0,-75.5,36.6], "ND": [-104.1,45.9,-96.5,49.0], "OH": [-84.8,38.4,-80.5,42.0],
    "OK": [-103.0,33.6,-94.4,37.0], "OR": [-124.5,42.0,-116.4,46.3], "PA": [-80.6,39.7,-74.7,42.3],
    "RI": [-71.9,41.1,-71.1,42.0], "SC": [-83.4,32.0,-78.5,35.2], "SD": [-104.1,42.5,-96.4,45.9],
    "TN": [-90.3,35.0,-81.6,36.7], "TX": [-106.7,25.8,-93.5,36.5], "UT": [-114.1,37.0,-109.0,42.0],
    "VT": [-73.5,42.7,-71.5,45.0], "VA": [-83.7,36.5,-75.2,39.5], "WA": [-124.8,45.5,-117.0,49.0],
    "WV": [-82.7,37.2,-77.8,40.6], "WI": [-92.9,42.5,-86.8,47.0], "WY": [-111.1,41.0,-104.0,45.0],
    "DC": [-77.2,38.8,-76.9,39.0],
}

# All religious primary categories observed in Overture
RELIGIOUS_CATEGORIES = {
    "place_of_worship",  # generic — includes many subcategories
    "church_cathedral", "cathedral",
    "baptist_church", "catholic_church", "episcopal_church",
    "pentecostal_church", "anglican_church", "evangelical_church",
    "lutheran_church", "methodist_church", "presbyterian_church",
    "orthodox_church", "mormon_church", "jehovahs_witness_kingdom_hall",
    "religious_organization", "religious_school", "religious_destination",
    "mission", "convents_and_monasteries", "monastery", "convent",
    "synagogue", "mosque", "temple", "hindu_temple", "buddhist_temple",
    "sikh_temple", "jain_temple",
    "meditation_center", "spiritual_center", "spiritual_shop",
    "wedding_chapel", "chapel",
    "faith_based_organization", "ministry",
    "parish", "diocese", "archdiocese",
    "seminary", "theological_school",
    "shrines", "shrine", "basilica",
    "ashram", "hermitage", "abbey",
    "gurdwara", "mandir",
    "kingdom_hall",
    "church", "worship_center",
}


def get_primary_cat(categories):
    """Extract primary category from Overture categories dict."""
    if isinstance(categories, dict):
        return categories.get("primary", "")
    return ""


def get_sub_cat(categories):
    """Extract subcategory from Overture categories dict."""
    if isinstance(categories, dict):
        return categories.get("subcategory", "")
    return ""


def query_state(state_code, bbox, out_dir):
    ts = datetime.now().strftime("%H:%M:%S")
    t0 = time.time()
    print(f"[{ts}] {state_code}: querying Overture...")
    try:
        reader = overturemaps.record_batch_reader(overture_type="place", bbox=bbox)
        df = reader.read_pandas()
    except Exception as e:
        print(f"  ERROR: {e}")
        return 0

    elapsed = time.time() - t0
    total = len(df)
    print(f"  {total:,} total places ({elapsed:.0f}s)")

    if total == 0:
        return 0

    # Extract primary category into a column
    df["prim_cat"] = df["categories"].apply(get_primary_cat)
    df["sub_cat"] = df["categories"].apply(get_sub_cat)

    # Filter: primary category is in our religious set
    # OR category contains religious keywords
    religious_mask = df["prim_cat"].str.lower().isin(RELIGIOUS_CATEGORIES)

    # Also catch: any category with the word "church", "worship", "temple" etc
    keyword_mask = df["prim_cat"].str.lower().str.contains(
        "church|worship|temple|mosque|synagogue|chapel|monastery|convent|"
        "shrine|mission|parish|diocese|religious|faith|kingdom.?hall|"
        "jehovah|cathedral|basilica|seminary|minister|evangelical|"
        "congregation|abbey|gurdwara|mandir|spiritual|prayer|meditation|"
        "ashram|hermitage|anglican|baptist|methodist|lutheran|"
        "presbyterian|orthodox|catholic|pentecostal|buddhist|hindu|"
        "islamic|muslim|jewish|salvation|gospel|ward|stake|lds|mormon",
        na=False
    )

    combined = religious_mask | keyword_mask
    rel_df = df[combined]
    rel_count = len(rel_df)

    print(f"  {rel_count:,} religious records ({rel_count/total*100:.1f}%)")

    if rel_count == 0:
        print(f"  No religious records found")
        return 0

    # Save
    records = []
    for _, row in rel_df.iterrows():
        n = row.get("names", {}) or {}
        pname = n.get("primary", "") if isinstance(n, dict) else ""
        ws = row.get("websites") or []
        ph = row.get("phones") or []
        addrs = row.get("addresses") or []
        addr = addrs[0] if len(addrs) > 0 else {}

        # Get centroid coords from bbox
        bbox_data = row.get("bbox")
        lat = lon = ""
        if isinstance(bbox_data, dict):
            min_lat = bbox_data.get("min_latitude")
            max_lat = bbox_data.get("max_latitude")
            min_lon = bbox_data.get("min_longitude")
            max_lon = bbox_data.get("max_longitude")
            if min_lat is not None and max_lat is not None:
                lat = (min_lat + max_lat) / 2
            if min_lon is not None and max_lon is not None:
                lon = (min_lon + max_lon) / 2

        records.append({
            "name": pname,
            "category": row.get("prim_cat", ""),
            "subcategory": row.get("sub_cat", ""),
            "website": ";".join(ws) if ws else "",
            "phone": ";".join(ph) if ph else "",
            "address": addr.get("freeform", ""),
            "city": addr.get("locality", ""),
            "state": addr.get("region", state_code),
            "zip": addr.get("postcode", ""),
            "latitude": lat,
            "longitude": lon,
        })

    out_path = os.path.join(out_dir, f"overture_religion_{state_code}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "name", "category", "subcategory", "website", "phone", "address",
            "city", "state", "zip", "latitude", "longitude"
        ])
        w.writeheader()
        w.writerows(records)

    print(f"  Saved {len(records)} records -> {out_path}")
    return rel_count


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", type=str, default="",
                        help="Comma-separated state codes (default: all)")
    parser.add_argument("--out", type=str, default="/home/ec2-user/data/overture_religion")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    states = [s.strip().upper() for s in args.states.split(",")] if args.states else sorted(STATE_BBOX.keys())

    total = 0
    for st in states:
        if st not in STATE_BBOX:
            print(f"Unknown state: {st}")
            continue
        count = query_state(st, STATE_BBOX[st], args.out)
        total += count
        # Brief pause between states
        time.sleep(1)

    # Merge all state files into one
    merged_path = os.path.join(args.out, "overture_religion_all.csv")
    all_records = []
    for st in states:
        fp = os.path.join(args.out, f"overture_religion_{st}.csv")
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                all_records.extend(list(reader))

    if all_records:
        with open(merged_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=all_records[0].keys())
            w.writeheader()
            w.writerows(all_records)
        print(f"\n{'='*60}")
        print(f"MERGED: {len(all_records):,} total religious records -> {merged_path}")
        print(f"{'='*60}")

        # Print category summary
        from collections import Counter
        cat_counts = Counter(r["category"] for r in all_records)
        print(f"\nCategory breakdown:")
        for cat, cnt in cat_counts.most_common(30):
            print(f"  {cat:40s}: {cnt:>8,}")
    else:
        print(f"\nNo religious records found.")


if __name__ == "__main__":
    main()

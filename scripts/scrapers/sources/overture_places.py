#!/usr/bin/env python3
"""
Overture Maps Places Query — runs on EC2 t3.medium
Queries Overture's open Places dataset for US places_of_worship with websites.
Saves results to CSV for cross-referencing with our DB.
"""
import csv, json, os, sys, time
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


def query_state(state_code, bbox, out_dir):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {state_code}: querying {bbox}...")
    try:
        reader = overturemaps.record_batch_reader(overture_type="place", bbox=bbox)
        df = reader.read_pandas()
    except Exception as e:
        print(f"  Error: {e}")
        return 0, 0

    total = len(df)
    if total == 0:
        return 0, 0

    # Filter to place_of_worship
    worship = df[df["categories"].apply(
        lambda c: c.get("primary") == "place_of_worship" if c else False
    )]
    wc = len(worship)
    print(f"  {total:,} total places, {wc:,} places_of_worship")

    # Filter to those with websites
    has_web = worship[worship["websites"].notna() &
                      (worship["websites"].apply(lambda x: len(x) > 0 if x is not None else False))]
    web_count = len(has_web)
    print(f"  With websites: {web_count:,}")

    if web_count > 0:
        out_path = os.path.join(out_dir, f"overture_{state_code}.csv")
        records = []
        for _, row in has_web.iterrows():
            names = row.get("names", {}) or {}
            pname = names.get("primary", "") if isinstance(names, dict) else ""
            ws = row.get("websites") or []
            ph = row.get("phones") or []
            addrs = row.get("addresses") or []
            addr = addrs[0] if len(addrs) > 0 else {}
            records.append({
                "name": pname,
                "website": ";".join(ws) if ws else "",
                "phone": ";".join(ph) if ph else "",
                "address": addr.get("freeform", ""),
                "city": addr.get("locality", ""),
            })
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["name","website","phone","address","city"])
            w.writeheader()
            w.writerows(records)
        print(f"  Saved {len(records)} to {out_path}")
    return wc, web_count


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--states", type=str, default="", help="Comma-separated")
    parser.add_argument("--out", type=str, default="/home/ec2-user/data/overture")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    states = [s.strip().upper() for s in args.states.split(",")] if args.states else list(STATE_BBOX.keys())
    tw, tb = 0, 0
    for st in states:
        if st in STATE_BBOX:
            w, b = query_state(st, STATE_BBOX[st], args.out)
            tw += w; tb += b
        else:
            print(f"Unknown: {st}")
    print(f"\nTotal: {tw:,} places_of_worship, {tb:,} with websites")


if __name__ == "__main__":
    main()

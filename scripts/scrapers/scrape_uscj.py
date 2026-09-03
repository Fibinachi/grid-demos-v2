"""
USCJ (United Synagogue of Conservative Judaism) Network Scraper
Scrapes all synagogues from uscj.org/network API endpoints.

API: https://uscj.org/wp-json/wp/v2/
- /districts — list all districts
- /nearest-locations?district={id} — get all synagogues for a district

Output: data/denom/uscj_synagogues.csv
"""

import requests
import csv
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from gw_db import get_db
    HAS_DB = True
except ImportError:
    HAS_DB = False

API_BASE = "https://uscj.org/wp-json/wp/v2"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "denom")
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "uscj_synagogues.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_json(endpoint, params=None):
    """Fetch JSON from USCJ API."""
    url = f"{API_BASE}/{endpoint}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    print("=" * 60)
    print("USCJ Synagogue Scraper")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    # 1. Get all districts
    print("\n[1/3] Fetching districts...")
    data = fetch_json("districts")
    districts = data.get("data", [])
    print(f"  Found {len(districts)} districts:")

    for d in districts:
        print(f"    id={d['id']:>4} | {d['title']}")

    # 2. Fetch synagogues for each district
    print(f"\n[2/3] Fetching synagogues for {len(districts)} districts...")
    all_synagogues = []
    seen_ids = set()

    for i, district in enumerate(districts):
        district_id = district["id"]
        district_name = district["title"]
        print(f"  [{i+1}/{len(districts)}] District {district_id}: {district_name}...", end=" ", flush=True)

        try:
            data = fetch_json("nearest-locations", params={"district": district_id})
            syns = data.get("data", [])
            new_count = 0
            for s in syns:
                if s["id"] not in seen_ids:
                    seen_ids.add(s["id"])
                    s["district_name"] = district_name
                    all_synagogues.append(s)
                    new_count += 1
            print(f"{len(syns)} returned, {new_count} new (total: {len(all_synagogues)})")
        except Exception as e:
            print(f"ERROR: {e}")

        if i < len(districts) - 1:
            time.sleep(0.5)  # Be polite

    print(f"\n  Total unique synagogues: {len(all_synagogues)}")

    # 3. Save to CSV
    print(f"\n[3/3] Saving to {OUTPUT_CSV}...")
    fieldnames = [
        "id", "title", "street1", "street2", "city", "state", "zip",
        "phone", "size", "latitude", "longitude", "url",
        "civicrmId", "district", "district_name", "facebookUrl"
    ]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_synagogues)

    print(f"  ✅ Saved {len(all_synagogues)} synagogues to {OUTPUT_CSV}")

    # 4. Print summary
    print("\n" + "=" * 60)
    print("Summary by District:")
    from collections import Counter
    district_counts = Counter(s["district_name"] for s in all_synagogues)
    for name, count in district_counts.most_common():
        print(f"  {name}: {count}")
    print(f"\n  TOTAL: {len(all_synagogues)} unique synagogues")
    print("=" * 60)


if __name__ == "__main__":
    main()

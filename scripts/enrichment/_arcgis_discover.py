"""Phase 1: Discover ALL ArcGIS worship datasets via the search API."""
import json, os, sys, time, urllib.request, urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARCGIS_DIR = os.path.join(BASE_DIR, "data", "arcgis")
os.makedirs(ARCGIS_DIR, exist_ok=True)
SEARCH_URL = "https://www.arcgis.com/sharing/rest/search"
RAW_PATH = os.path.join(ARCGIS_DIR, "arcgis_catalog_raw.json")

def search_arcgis(query, start=1, num=100):
    params = {"q": query, "f": "json", "num": num, "start": start, "sortField": "numViews", "sortOrder": "desc"}
    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    queries = [
        "worship type:\"Feature Service\"",
        "\"places of worship\" type:\"Feature Service\"",
        "\"place of worship\" type:\"Feature Service\"",
        "church type:\"Feature Service\"",
        "\"house of worship\" type:\"Feature Service\"",
        "\"religious institution\" type:\"Feature Service\"",
    ]
    all_results = []
    seen_ids = set()

    for q in queries:
        start = 1
        while True:
            data = search_arcgis(q, start=start)
            results = data.get("results", [])
            total = data.get("total", 0)
            new_count = 0
            for r in results:
                rid = r.get("id")
                if rid and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_results.append(r)
                    new_count += 1
            print(f'  Q={q[:40]} @{start}: {new_count} new ({len(all_results):,} total, {total} avail)')
            if len(results) < 100:
                break
            start += 100
            time.sleep(0.5)

    out = {
        "pipeline_version": "1.0",
        "pipeline_date": datetime.now().isoformat(),
        "total_datasets": len(all_results),
        "datasets": all_results,
    }
    with open(RAW_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"\nSaved {len(all_results):,} datasets to {RAW_PATH}")

if __name__ == "__main__":
    main()

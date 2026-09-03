import urllib.request, json, time

# Get 2018 + 2012 + 2017 dataset resource IDs
for year, dataset_id in [
    ("2018", "206f5517-12c3-40e0-9494-c75d2e410c64"),
    ("2017", "38a2cce2-3639-43f9-ab59-8097b202e57e"),
    ("2012", "66217614-917b-4df9-a5c0-19760f318e23"),
    ("2011", "8e4fbdda-f73e-4c49-b0f3-79b86d4a81fb"),
]:
    url = f"https://open.canada.ca/data/api/action/package_show?id={dataset_id}"
    time.sleep(1.5)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read())
    pkg = data["result"]
    
    # Find Identification CSV
    for r in pkg["resources"]:
        name = r.get("name", "").lower()
        if "identification" in name and r.get("format") == "CSV":
            print(f"{year}: ID={r['id']}, Size={r.get('size','?')}, Name={r['name'][:60]}")
            # The download URL pattern
            print(f"  URL: /data/dataset/{dataset_id}/resource/{r['id']}")
            print()
            break
    else:
        # List all CSV resources
        print(f"{year}: No 'Identification' CSV found. Resources:")
        for r in pkg["resources"]:
            if r.get("format") == "CSV":
                print(f"  [{r['id']}] {r['name'][:80]} (size={r.get('size','?')})")
        print()

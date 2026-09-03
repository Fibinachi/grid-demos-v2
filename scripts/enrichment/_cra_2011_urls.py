import urllib.request, json, time

# Get 2011 dataset package details — need full resource URLs
dataset_id = "8e4fbdda-f73e-4c49-b0f3-79b86d4a81fb"
url = f"https://open.canada.ca/data/api/action/package_show?id={dataset_id}"

time.sleep(2)
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})
data = json.loads(urllib.request.urlopen(req, timeout=30).read())
pkg = data["result"]
print(f"Dataset: {pkg['title']}")
print(f"Resources: {len(pkg['resources'])}\n")

for r in pkg["resources"]:
    fmt = r.get("format", "?")
    name = r.get("name", "?")[:80]
    res_url = r.get("url", "")
    # Full CKAN download URL
    res_id = r["id"]
    dl_url = f"https://open.canada.ca/data/dataset/{dataset_id}/resource/{res_id}/download/{name}.csv"
    size = r.get("size", "?")
    print(f"  [{fmt}] {name}")
    print(f"    ID: {res_id}")
    print(f"    Size: {size}")
    print(f"    URL: {res_url[:120]}")
    print(f"    DL:  {dl_url[:140]}")
    print()

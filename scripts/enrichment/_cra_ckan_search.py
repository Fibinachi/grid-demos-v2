import urllib.request, json, time

# CKAN API — search for CRA charities dataset
url = "https://open.canada.ca/data/api/action/package_search?q=charities+listings&rows=10"
print("Searching CKAN for charities datasets...")
time.sleep(2)

req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    results = data.get("result", {}).get("results", [])
    print(f"Found {len(results)} datasets:\n")
    for r in results:
        print(f"  ID: {r['id']}")
        print(f"  Title: {r.get('title', '?')[:120]}")
        resources = r.get("resources", [])
        for res in resources:
            fmt = res.get("format", "?")
            url_r = res.get("url", "")[:100]
            name = res.get("name", "")[:80]
            print(f"    [{fmt}] {name} -> {url_r}")
        print()
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")

import urllib.request, json, time

# Search for "T3010" or "registered charity" — current data
for query in ["T3010", "registered charity information return"]:
    url = f"https://open.canada.ca/data/api/action/package_search?q={urllib.request.quote(query)}&rows=5"
    print(f"\n=== Searching: {query} ===")
    time.sleep(2)
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        results = data.get("result", {}).get("results", [])
        print(f"Found {len(results)} datasets:")
        for r in results:
            title = r.get("title", "?")
            print(f"  [{r['id']}] {title[:120]}")
            # Look for CSV resources
            for res in r.get("resources", []):
                fmt = res.get("format", "N/A")
                if fmt in ("CSV", "ZIP", "XML"):
                    res_url = res.get("url", "")
                    name = res.get("name", "")[:80]
                    print(f"    [{fmt}] {name}")
                    print(f"    URL: {res_url[:120]}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

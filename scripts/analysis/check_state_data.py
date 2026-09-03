"""Check state open data portals for charity registration datasets."""
import urllib.request, json, sys

portals = [
    ("CA", "https://data.ca.gov/api/3/action/package_search?q=charitable+trust+registry+email"),
    ("CA", "https://data.ca.gov/api/3/action/package_search?q=charitable+organization+registration"),
    ("NY", "https://data.ny.gov/api/3/action/package_search?q=charities+registration"),
    ("NY", "https://data.ny.gov/api/3/action/package_search?q=nonprofit+registry"),
    ("TX", "https://data.texas.gov/api/3/action/package_search?q=charitable+organization"),
    ("TX", "https://data.texas.gov/api/3/action/package_search?q=nonprofit+registration"),
]

for state, url in portals:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            count = data.get("result", {}).get("count", 0)
            results = data.get("result", {}).get("results", [])
            print(f"[{state}] {count} datasets for {url.split('q=')[1][:60]}")
            for ds in results[:2]:
                title = ds.get("title", "?")
                notes = ds.get("notes", "")[:120]
                print(f"  -> {title}: {notes}")
    except Exception as e:
        print(f"[{state}] ERROR: {str(e)[:80]}")

print()
print("=== Direct state registry checks ===")

# Also check if these states have direct registry URLs
registries = [
    ("CA AG", "https://rct.doj.ca.gov/Verification/Web/Search.aspx?Facility=Y"),
    ("NY Charities", "https://www.charitiesnys.com/registration_search.jsp"),
    ("TX SOS", "https://direct.sos.state.tx.us/help/help-corp.asp"),
]

for name, url in registries:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")[:500]
            print(f"[{name}] Reachable: YES")
            # Check if it has a search form
            if "search" in html.lower() or "ein" in html.lower():
                print("  -> Has search form")
    except Exception as e:
        print(f"[{name}] Reachable: NO - {str(e)[:60]}")

import urllib.request, json

# Test the API directly with the browser URL format
url = "https://projects.propublica.org/nonprofits/api/v2/search.json?q=saddleback+church"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    orgs = data.get("organizations", [])
    print(f"Found {len(orgs)} orgs")
    for o in orgs[:3]:
        print(f"  {o['name']} (EIN: {o['ein']})")
except Exception as e:
    print(f"Search failed: {e}")

# Also test the IRS Direct API
url2 = "https://apps.irs.gov/app/eos/api/v1/eoss?ein=521145718"
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req2, timeout=10) as r:
        print(f"\nIRS API: {r.read().decode()[:500]}")
except Exception as e:
    print(f"\nIRS API failed: {e}")

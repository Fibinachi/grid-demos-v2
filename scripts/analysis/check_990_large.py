import urllib.request, json

# Try larger churches/orgs that definitely file 990s
large_eins = [
    "952543986",  # Saddleback Church (Rick Warren's) - very large
    "363185520",  # Willow Creek Association
    "521145718",  # Billy Graham Evangelistic Association
]

for ein in large_eins:
    url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"EIN {ein}: Failed - {e}")
        continue
    
    org = data["organization"]
    print(f"\n{'='*60}")
    print(f"{org['name']} (EIN: {ein})")
    print(f"{'='*60}")
    print(f"  Revenue: {org.get('revenue_amount')}")
    print(f"  Income:  {org.get('income_amount')}")
    print(f"  Assets:  {org.get('asset_amount')}")
    print(f"  Filing req code: {org.get('filing_requirement_code')}")
    print(f"  # filings with data: {len(data.get('filings_with_data', []))}")
    
    filings = data.get("filings_with_data", [])
    if filings:
        f = filings[0]
        print(f"\n  --- Latest Filing Data ---")
        for key, val in sorted(f.items()):
            if val is not None and val != "":
                print(f"    {key}: {val}")

import urllib.request, json

eins = [
    "363886435",  # Praise Temple (small church)
    "461511800",  # Clarity Church
    "980052462",  # Cornerstone Baptist
]

for ein in eins:
    url = f"https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
    except:
        print(f"EIN {ein}: Failed to fetch")
        continue
    
    org = data["organization"]
    print(f"\n=== {org['name']} (EIN: {ein}) ===")
    print(f"  Revenue: {org.get('revenue_amount')}")
    print(f"  Income:  {org.get('income_amount')}")
    print(f"  Assets:  {org.get('asset_amount')}")
    print(f"  Filing req code: {org.get('filing_requirement_code')}")
    print(f"  Filings WITH data: {len(data.get('filings_with_data', []))}")
    print(f"  Filings WITHOUT data: {len(data.get('filings_without_data', []))}")
    
    # Show latest filing details if available
    filings = data.get("filings_with_data", [])
    if filings:
        f = filings[0]
        print(f"  Latest filing ({f.get('tax_prd', '?')}):")
        print(f"    Total Revenue:  {f.get('totrevenue', 'N/A')}")
        print(f"    Total Expenses: {f.get('totfuncexpns', 'N/A')}")
        print(f"    Total Assets:   {f.get('totassetsend', 'N/A')}")
        print(f"    Contributions:  {f.get('contribution', 'N/A')}")
        print(f"    Program Rev:    {f.get('progservrev', 'N/A')}")
        print(f"    Invest Income:  {f.get('investincome', 'N/A')}")
        print(f"    Officer Comp:   {f.get('compensation', 'N/A')}")
        print(f"    Employees:      {f.get('employees', 'N/A')}")
        print(f"    Program %:      {f.get('progservpercent', 'N/A')}")

# Also test ProPublica's full filing detail endpoint
print("\n\n=== Full filing detail test ===")
url2 = "https://projects.propublica.org/nonprofits/api/v2/organizations/363886435/full_filing.json"
req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req2, timeout=10) as r:
        detail = json.loads(r.read().decode())
    # Print all available fields
    for key, val in detail.items():
        if isinstance(val, (str, int, float, bool)) and val:
            print(f"  {key}: {val}")
except Exception as e:
    print(f"Full filing failed: {e}")

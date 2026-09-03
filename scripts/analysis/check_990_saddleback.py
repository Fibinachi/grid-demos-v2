import urllib.request, json

# Try Saddleback Valley Community Church (likely Saddleback proper)
url = "https://projects.propublica.org/nonprofits/api/v2/organizations/953689195.json"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())

org = data["organization"]
print(f"{org['name']} (EIN: {org['ein']})")
print(f"  Revenue: {org.get('revenue_amount')}")
print(f"  Assets:  {org.get('asset_amount')}")
print(f"  Filing req: {org.get('filing_requirement_code')}")
print(f"  Filings with data: {len(data.get('filings_with_data', []))}")

filings = data.get("filings_with_data", [])
if filings:
    f = filings[0]
    print(f"\n=== Latest Filing ===")
    for key, val in sorted(f.items()):
        if val is not None and str(val).strip():
            print(f"  {key}: {val}")

# Also check what percentage of churches in our DB might have filings
# Filing req code 1 = must file, codes 6+ = exempt
print(f"\n\n=== Filing Requirement Codes ===")
codes = {
    1: "Must file 990 (gross receipts >= $200K or assets >= $500K)",
    2: "Must file 990-EZ (gross receipts $50K-$200K)",
    3: "Must file 990-N (e-postcard, gross receipts < $50K)",
    4: "Group return",
    5: "Church/org not required to file",
    6: "Church/org not required to file (different category)",
    7: "Unknown",
    8: "Foreign org",
    9: "Government",
}
for code, desc in sorted(codes.items()):
    print(f"  {code}: {desc}")

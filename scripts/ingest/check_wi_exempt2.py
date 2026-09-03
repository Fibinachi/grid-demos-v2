"""Query WI parcels with AUXCLASS = TAX EXEMPT."""
import requests
from collections import Counter

url = "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/Wisconsin_Statewide_Parcels_DB/FeatureServer/0/query"

# Query for tax exempt class
params = {
    "f": "json",
    "where": "AUXCLASS = 'TAX EXEMPT'",
    "outFields": "OWNERNME1,PROPCLASS,AUXCLASS,ESTFMKVALUE,NETPRPTA,CNTASSDVALUE,CONAME,SITEADRESS",
    "orderByFields": "ESTFMKVALUE DESC",
    "resultRecordCount": 30,
    "returnCountOnly": "false",
}

r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
data = r.json()

count = data.get("features", [])
print(f"Returned: {len(count)} features")

for f in count:
    attrs = f["attributes"]
    owner = (attrs.get("OWNERNME1") or "")[:55]
    addr = (attrs.get("SITEADRESS") or "")[:55]
    value = attrs.get("ESTFMKVALUE", 0)
    pc = attrs.get("PROPCLASS", "")
    county = attrs.get("CONAME", "")
    print(f"  ${value:>12,.0f} | PC={str(pc):8s} | {county:15s} | {owner}")
    if addr:
        print(f"  {'':>12} | {'':8s} | {'':15s} | {addr}")

# Also count total
params2 = {**params, "returnCountOnly": "true"}
r2 = requests.get(url, params=params2, headers={"User-Agent": "Mozilla/5.0"})
try:
    total = r2.json().get("count", 0)
    print(f"\nTotal TAX EXEMPT parcels statewide: {total:,}")
except:
    pass

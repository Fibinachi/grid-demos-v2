"""Find tax-exempt parcel patterns in WI."""
import requests, json
from collections import Counter

url = "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/Wisconsin_Statewide_Parcels_DB/FeatureServer/0/query"

# Query parcels with zero net property tax (fully exempt)
params = {
    "f": "json",
    "where": "NETPRPTA = 0 AND ESTFMKVALUE > 10000",
    "outFields": "OWNERNME1,PROPCLASS,AUXCLASS,ESTFMKVALUE,NETPRPTA,CNTASSDVALUE,CONAME,PLACENAME",
    "orderByFields": "ESTFMKVALUE DESC",
    "resultRecordCount": 30,
}

r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
data = r.json()

print(f"Query returned {len(data.get('features', []))} features")

pc_counter = Counter()
ac_counter = Counter()

for f in data.get("features", []):
    attrs = f["attributes"]
    owner = attrs.get("OWNERNME1", "")[:50]
    propclass = attrs.get("PROPCLASS", "")
    auxclass = attrs.get("AUXCLASS", "")
    value = attrs.get("ESTFMKVALUE", 0)
    county = attrs.get("CONAME", "")
    
    pc_counter[str(propclass)] += 1
    if auxclass:
        ac_counter[str(auxclass)] += 1
    
    print(f"  {value:>12,.0f} | PC={str(propclass):10s} AC={str(auxclass):15s} | {county:15s} | {owner}")

print()
print("PROPCLASS distribution:")
for k, v in pc_counter.most_common():
    print(f"  {k:20s} {v}")

print()
print("AUXCLASS distribution:")
for k, v in ac_counter.most_common():
    print(f"  {k:20s} {v}")

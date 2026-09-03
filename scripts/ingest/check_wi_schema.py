import requests, json

url = "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/Wisconsin_Statewide_Parcels_DB/FeatureServer/0?f=json"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
data = r.json()

print(f"Layer: {data.get('name', '?')}")
print(f"Fields: {len(data.get('fields', []))}")
print()

for f in data.get("fields", []):
    name = f["name"]
    ftype = f["type"]
    alias = f.get("alias", "")
    print(f"  {name:35s} {ftype:12s} {alias}")

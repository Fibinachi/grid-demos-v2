"""Check WI parcel AUXCLASS and PROPCLASS values for religious filtering."""
import requests, json
from collections import Counter

# Query a sample of parcels to see AUXCLASS/PROPCLASS values
url = "https://services3.arcgis.com/n6uYoouQZW75n5WI/arcgis/rest/services/Wisconsin_Statewide_Parcels_DB/FeatureServer/0/query"

# Get distinct AUXCLASS values
params = {
    "f": "json",
    "where": "1=1",
    "returnDistinctValues": "true",
    "outFields": "AUXCLASS",
    "groupByFieldsForStatistics": "AUXCLASS",
    "orderByFields": "AUXCLASS",
    "resultRecordCount": 50,
}

r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
try:
    data = r.json()
    if "features" in data:
        aux_values = []
        for f in data["features"]:
            aux_values.append(f["attributes"].get("AUXCLASS", ""))
        
        aux_counter = Counter(aux_values)
        print("AUXCLASS values (from sample):")
        for val, cnt in aux_counter.most_common(20):
            print(f"  {str(val):30s} {cnt:6,}")
    else:
        print("Response:", json.dumps(data, indent=2)[:500])
except Exception as e:
    print(f"Error: {e}")

# Also try PROPCLASS
print()
params2 = {**params, "outFields": "PROPCLASS", "groupByFieldsForStatistics": "PROPCLASS"}
r2 = requests.get(url, params=params2, headers={"User-Agent": "Mozilla/5.0"})
try:
    data2 = r2.json()
    if "features" in data2:
        for f in data2["features"]:
            print(f"  PROPCLASS: {f['attributes'].get('PROPCLASS','')}")
    else:
        print("PROPCLASS response:", json.dumps(data2, indent=2)[:300])
except Exception as e:
    print(f"Error: {e}")

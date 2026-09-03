"""Explore WA FeatureServer for parcel data."""
import urllib.request, json

# WA FeatureServer
url = 'https://services6.arcgis.com/rWgPxEaLomdfVkLw/arcgis/rest/services/WA_Statewide_Parcels/FeatureServer?f=json'
req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())

print('WA Statewide Parcels FeatureServer:')
print(f'  Description: {data.get("serviceDescription", "N/A")[:120]}')
print(f'  Document Info: {data.get("documentInfo", {})}')
print(f'  Layers: {len(data.get("layers", []))}')
for layer in data.get('layers', []):
    print(f'  Layer {layer["id"]}: {layer["name"]} ({layer.get("geometryType","?")}) - {layer.get("description","")[:80]}')

# Try querying the first layer for fields
if data.get('layers'):
    l0 = data['layers'][0]
    layer_url = f'https://services6.arcgis.com/rWgPxEaLomdfVkLw/arcgis/rest/services/WA_Statewide_Parcels/FeatureServer/{l0["id"]}?f=json'
    req2 = urllib.request.Request(layer_url, headers={'User-Agent': 'GRID/1.0'})
    layer_data = json.loads(urllib.request.urlopen(req2, timeout=15).read().decode())
    print(f'\n  Layer 0 fields (first 20):')
    for field in layer_data.get('fields', [])[:20]:
        print(f'    {field["name"]:30s} {field["type"]:10s}')
    print(f'  Supports advanced queries: {layer_data.get("advancedQueryCapabilities",{}).get("supportsPagination","?")}')

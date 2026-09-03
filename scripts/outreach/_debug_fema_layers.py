"""Debug ArcGIS FEMA layer structure."""
import urllib.request, json

# Top-level FeatureServer
url = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer?f=json'
req = urllib.request.Request(url, headers={'User-Agent':'GRID/1.0'})
r = urllib.request.urlopen(req, timeout=15)
d = json.loads(r.read())
print(f'Layers: {len(d.get("layers",[]))}')
for layer in d.get('layers',[]):
    print(f'  Layer {layer["id"]}: {layer["name"]}')

# Test Layer 0 count
url2 = url.replace('?f=json', '/0/query?where=1%3D1&returnCountOnly=true&f=json')
req2 = urllib.request.Request(url2, headers={'User-Agent':'GRID/1.0'})
try:
    r2 = urllib.request.urlopen(req2, timeout=15)
    d2 = json.loads(r2.read())
    print(f'\nLayer 0 count query: {d2.get("count", "NO COUNT")}')
    if 'error' in d2:
        print(f'Error: {d2["error"]}')
except Exception as e:
    print(f'\nLayer 0 query failed: {e}')

# Try querying with a small batch to test
url3 = url.replace('?f=json', '/0/query?where=1%3D1&outFields=*&returnGeometry=false&resultRecordCount=2&f=json')
req3 = urllib.request.Request(url3, headers={'User-Agent':'GRID/1.0'})
try:
    r3 = urllib.request.urlopen(req3, timeout=15)
    d3 = json.loads(r3.read())
    if 'features' in d3:
        print(f'\nSample query OK: {len(d3["features"])} features returned')
        if d3['features']:
            print(f'Fields: {list(d3["features"][0]["attributes"].keys())[:10]}')
    elif 'error' in d3:
        print(f'\nSample query error: {d3["error"]}')
except Exception as e:
    print(f'\nSample query failed: {e}')

"""Test alternate download URLs for NY, NJ, WA, WI statewide parcels."""
import urllib.request, os, json, time

def test_url(url, desc):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        ct = resp.headers.get('Content-Type', '')
        cl = resp.headers.get('Content-Length', '?')
        size_mb = int(cl) / (1024*1024) if cl.isdigit() else 0
        print(f'  OK [{resp.status}] {size_mb:.0f}MB — {desc}')
        return True
    except Exception as e:
        err = str(e)[:100]
        print(f'  FAIL: {desc} — {err}')
        return False

print('=== NY — Open Data API v3 ===')
test_url('https://opendata.arcgis.com/api/v3/datasets/b5acd52aace0498f8953f583c5d1e619/downloads/data?format=geojson&spatialRefId=4326', 'NY GeoJSON')
test_url('https://opendata.arcgis.com/api/v3/datasets/b5acd52aace0498f8953f583c5d1e619/downloads/data?format=shp&spatialRefId=4326', 'NY Shapefile')
test_url('https://opendata.arcgis.com/api/v3/datasets/b5acd52aace0498f8953f583c5d1e619/downloads/data?format=csv&spatialRefId=4326', 'NY CSV')

print()
print('=== NJ — Open Data API v3 ===')
test_url('https://opendata.arcgis.com/api/v3/datasets/406cf6860390467d9f328ed19daa359d/downloads/data?format=geojson&spatialRefId=4326', 'NJ GeoJSON')
test_url('https://opendata.arcgis.com/api/v3/datasets/406cf6860390467d9f328ed19daa359d/downloads/data?format=shp&spatialRefId=4326', 'NJ Shapefile')

print()
print('=== WA — try FeatureServer ===')
# Try to query the WA parcels FeatureServer for a small sample
test_url('https://services6.arcgis.com/rWgPxEaLomdfVkLw/arcgis/rest/services/WA_Statewide_Parcels/FeatureServer?f=json', 'WA FeatureServer info')

print()
print('=== WI — SCO Parcel MapServer ===')
try:
    req = urllib.request.Request('https://maps.sco.wisc.edu/arcgis/rest/services/Parcels/Statewide_V8/MapServer?f=json', headers={'User-Agent': 'GRID/1.0'})
    data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
    desc = data.get('serviceDescription', data.get('description', '?'))
    layers = data.get('layers', [])
    print(f'  OK: {desc[:80]}')
    for layer in layers:
        print(f'    Layer {layer["id"]}: {layer["name"]} ({layer.get("geometryType","?")})')
except Exception as e:
    print(f'  FAIL: {e}')

print()
print('=== MD — check downloaded ===')
md_csv = r'E:\grid\data\sources\MD_parcels\md_real_property_assessments.csv'
if os.path.exists(md_csv):
    sz_gb = os.path.getsize(md_csv) / (1024**3)
    print(f'  OK: {sz_gb:.1f} GB — MD SDAT assessments')
    # Count lines
    with open(md_csv, 'r', encoding='utf-8', errors='replace') as f:
        for i, _ in enumerate(f):
            if i >= 5:
                break
        print(f'  First 5 lines read OK')
else:
    print(f'  NOT FOUND: {md_csv}')

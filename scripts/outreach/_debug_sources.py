"""Debug FEMA/FBI data source connectivity."""
import urllib.request, json

# Test ArcGIS
print("=== FEMA ArcGIS ===")
urls = [
    'https://services.arcgis.com/XSeYKQzfXnEgLU9u/arcgis/rest/services/NRI_Tract_December2025/FeatureServer/0?f=json',
    'https://services.arcgis.com/XSeYKQzfXnEgLU9u/arcgis/rest/services?f=json',
]
for url in urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if 'error' in data:
                print(f'  ERROR: {url[:80]}')
                print(f'    {str(data.get("error",{}))[:120]}')
            else:
                print(f'  OK: {url[:80]}')
                if 'layers' in data:
                    for layer in data['layers']:
                        print(f'    Layer: {layer.get("name","?")} ({layer.get("id","?")})')
                else:
                    print(f'    Keys: {list(data.keys())[:10]}')
    except Exception as e:
        print(f'  FAIL: {url[:80]}')
        print(f'    {e}')

# Test FBI CDE
print("\n=== FBI CDE API ===")
fbi_urls = [
    'https://api.ucr.cjis.gov/api/states?page=1&per_page=5',
    'https://api.ucr.cjis.gov/api/agencies/count',
]
for url in fbi_urls:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID/1.0', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            print(f'  OK: {url[:80]}')
            print(f'    Keys: {list(data.keys())[:10]}')
            if 'results' in data:
                print(f'    Results: {len(data["results"])} items')
    except Exception as e:
        print(f'  FAIL: {url[:80]}')
        print(f'    {e}')

print("\nDone.")

"""Fix failed downloads from indigenous sites batch."""
import urllib.request
import json
import os

DEST = r"E:\grid\data\sources\indigenous"
os.makedirs(DEST, exist_ok=True)

def download(url, filename, desc):
    outpath = os.path.join(DEST, filename)
    if os.path.exists(outpath):
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"  SKIP (exists, {size_mb:.1f} MB): {desc}")
        return outpath
    print(f"  DOWNLOADING: {desc} ...", flush=True)
    try:
        urllib.request.urlretrieve(url, outpath)
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"  OK: {size_mb:.1f} MB — {filename}", flush=True)
        return outpath
    except Exception as e:
        print(f"  FAILED: {e}", flush=True)
        return None

def download_json(url, filename, desc):
    outpath = os.path.join(DEST, filename)
    if os.path.exists(outpath):
        print(f"  SKIP (exists): {desc}")
        return True
    print(f"  FETCHING: {desc} ...", flush=True)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GRID-Project/1.0'})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"  OK: {size_mb:.1f} MB — {filename}", flush=True)
        return True
    except Exception as e:
        print(f"  FAILED: {e}", flush=True)
        return False

# 1. UNESCO World Heritage — correct CSV URL
print("=== UNESCO WORLD HERITAGE ===")
download(
    "https://ihp-wins.unesco.org/dataset/88c8eff6-b94d-4826-bb13-7107ac4c02a9/resource/2f46f6b2-45f9-402b-ace9-1e02c9c97a3d/download/whc-sites-2025.csv",
    "whc-sites-2025.csv",
    "UNESCO World Heritage Sites 2025 (CSV)"
)

# 2. UNESCO World Heritage — JSON from whc.unesco.org API
# Try the official list endpoint
download_json(
    "https://whc.unesco.org/en/list/json/",
    "unesco_whc_list.json",
    "UNESCO WHC List (official JSON)"
)

# 3. MayaForestGIS — archaeological sites (ArcGIS Hub)
print()
print("=== MAYAN ARCHAEOLOGICAL SITES ===")
download(
    "https://opendata.arcgis.com/api/v3/datasets/c141bd0f90a94a7d84b5c927253986a8/downloads/data?format=geojson&spatialRefId=4326",
    "maya_forest_gis_sites.geojson",
    "MayaForestGIS Archaeological Sites (GeoJSON)"
)

# 4. Mayan sites from Data Basin  
download(
    "https://databasin.org/datasets/3aa6b24c882144d6a4197bd277ae753d",
    "mayan_sites_databasin.html",
    "Mayan Sites Data Basin (page)"
)

# 5. South American cultural sites — try alternate URL
print()
print("=== SOUTH AMERICAN ARCHAEOLOGICAL SITES ===")
download(
    "https://services1.arcgis.com/ce43NL50KQHI0qum/arcgis/rest/services/South_American_Cultural_Sites/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson",
    "south_american_cultural_sites.geojson",
    "South American Cultural Sites (ArcGIS FeatureServer GeoJSON)"
)

# 6. UNESCO Intangible Cultural Heritage
print()
print("=== UNESCO INTANGIBLE HERITAGE ===")
# Direct JSON API endpoint
download_json(
    "https://ich.unesco.org/en/lists?format=json&multinational=3",
    "unesco_ich_list.json",
    "UNESCO Intangible Heritage List (JSON)"
)

# Summary
print()
print("=== FINAL FILE LIST ===")
total = 0
for f in sorted(os.listdir(DEST)):
    fpath = os.path.join(DEST, f)
    if os.path.isfile(fpath):
        sz = os.path.getsize(fpath) / (1024 * 1024)
        total += sz
        print(f"  {sz:8.1f} MB  {f}")
print(f"\n  Total: {total:.1f} MB  |  {DEST}")

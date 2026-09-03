"""
Download all indigenous/ancient/archaeological worship site datasets.
Pleiades (ancient), Native Land Digital (indigenous territories),
UNESCO World Heritage, UNESCO Intangible Heritage, Mayan sites, and African WH sites.
"""
import urllib.request
import urllib.error
import json
import os
import time
import zipfile
import shutil

DEST = r"E:\grid\data\sources\indigenous"
os.makedirs(DEST, exist_ok=True)

def download(url, filename, desc):
    """Download a file with progress reporting."""
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
        # Clean up partial download
        if os.path.exists(outpath):
            os.remove(outpath)
        return None

def download_json(url, filename, desc):
    """Download JSON data and save it."""
    outpath = os.path.join(DEST, filename)
    if os.path.exists(outpath):
        size_mb = os.path.getsize(outpath) / (1024 * 1024)
        print(f"  SKIP (exists, {size_mb:.1f} MB): {desc}")
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

# ============================================================
# 1. PLEIADES — Ancient places gazetteer (CC BY 3.0)
#    v4.1: 41,480 places — temples, sanctuaries, shrines, altars
#    GitHub release: https://github.com/isawnyu/pleiades.datasets/releases
# ============================================================
print("=" * 60)
print("1. PLEIADES — Ancient Places Gazetteer")
print("=" * 60)

pleiades_urls = [
    # Primary: GitHub release v4.1 (28 May 2025)
    ("https://github.com/isawnyu/pleiades.datasets/archive/refs/tags/v4.1.zip",
     "pleiades_datasets_v4.1.zip", "Pleiades v4.1 (GitHub release, 41,480 places)"),
    # Also grab the latest GIS CSV package
    ("https://atlantides.org/downloads/pleiades/gis/pleiades_gis_data.zip",
     "pleiades_gis_data.zip", "Pleiades GIS CSV package"),
    # Latest JSON dump  
    ("https://atlantides.org/downloads/pleiades/json/pleiades-places-latest.json.gz",
     "pleiades_places_latest.json.gz", "Pleiades JSON dump (latest)"),
]

for url, fname, desc in pleiades_urls:
    download(url, fname, desc)

# ============================================================
# 2. NATIVE LAND DIGITAL — Indigenous territories worldwide
#    Territories, languages, and treaties polygons
#    API: https://native-land.ca/api/
# ============================================================
print()
print("=" * 60)
print("2. NATIVE LAND DIGITAL — Indigenous Territories")
print("=" * 60)

# Try API without key first (rate-limited but may work for territories)
nld_categories = [
    ("territories", "native_land_territories.geojson"),
    ("languages", "native_land_languages.geojson"),
    ("treaties", "native_land_treaties.geojson"),
]

for category, fname in nld_categories:
    url = f"https://native-land.ca/api/polygons/geojson/{category}"
    download_json(url, fname, f"Native Land Digital — {category}")

# Also try the ArcGIS Hub layer as alternate source
download(
    "https://opendata.arcgis.com/api/v3/datasets/e46f229101f3438fbe123374e14f98f4_0/downloads/data?format=geojson&spatialRefId=4326",
    "native_land_arcgis.geojson",
    "Native Land Digital — ArcGIS Hub GeoJSON"
)

# ============================================================
# 3. UNESCO WORLD HERITAGE LIST — 1,248 sites
#    Cultural + Natural + Mixed, includes temples, churches, mosques
# ============================================================
print()
print("=" * 60)
print("3. UNESCO WORLD HERITAGE LIST")
print("=" * 60)

# UNESCO IHP-WINS CSV (2025 list, includes coordinates and categories)
download(
    "https://ihp-wins.unesco.org/dataset/3d28e46f-dc06-44e3-8c8e-62ced26d3ba2/resource/6e3f7310-3c8e-40d5-8962-ce9084162fae/download/world-heritage-site-list-2025.csv",
    "unesco_world_heritage_2025.csv",
    "UNESCO World Heritage List 2025 (CSV)"
)

# Also try the UNESCO DataHub API
download_json(
    "https://api.unesco.org/whc/v1/list?format=json",
    "unesco_whc_list.json",
    "UNESCO World Heritage List (API JSON)"
)

# ============================================================
# 4. UNESCO INTANGIBLE CULTURAL HERITAGE
#    Rituals, oral traditions, indigenous practices
# ============================================================
print()
print("=" * 60)
print("4. UNESCO INTANGIBLE CULTURAL HERITAGE")
print("=" * 60)

download_json(
    "https://ich.unesco.org/en/open-access-to-dive-data-01218",
    "unesco_ich_dive.json",
    "UNESCO Intangible Heritage — DIVE dataset"
)

# ============================================================
# 5. MAYAN ARCHAEOLOGICAL SITES (Kaggle)
#    332 Mayan sites with inscriptions
# ============================================================
print()
print("=" * 60)
print("5. MAYAN ARCHAEOLOGICAL SITES")
print("=" * 60)

# Kaggle: 332 Mayan sites across Mexico, Guatemala, Belize, Honduras
# Direct download may need Kaggle API; try the raw CSV from GitHub mirrors
download(
    "https://raw.githubusercontent.com/ujwalkandi/Archaeological-Sites-with-May-a-Inscriptions/main/Mayan_Sites.csv",
    "mayan_sites.csv",
    "Mayan Archaeological Sites (332 sites, Kaggle)"
)

# ============================================================
# 6. ANCIENT LOCATIONS — South American & global archaeological sites
# ============================================================
print()
print("=" * 60)
print("6. ANCIENT LOCATIONS DATABASE")
print("=" * 60)

# South American cultural sites from ancientlocations.net
download(
    "https://opendata.arcgis.com/api/v3/datasets/tga::south-american-cultural-sites/downloads/data?format=csv&spatialRefId=4326",
    "south_american_cultural_sites.csv",
    "South American Cultural Sites (ancientlocations.net via ArcGIS)"
)

# ============================================================
# 7. MEGA MARS — World Temples Database (if accessible)
# ============================================================
print()
print("=" * 60)
print("7. TEMPLES / SACRED SITES DATABASES")
print("=" * 60)

# Wikidata SPARQL query for all temples, shrines, sacred sites worldwide
# Using a pre-built query that returns CSV
sparql_query = """
SELECT ?item ?itemLabel ?country ?countryLabel ?coord ?type ?typeLabel WHERE {
  ?item wdt:P31 ?type.
  ?type wdt:P279* wd:Q44539.  # subclass of religious building
  OPTIONAL { ?item wdt:P17 ?country. }
  OPTIONAL { ?item wdt:P625 ?coord. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 500000
"""

# Save the SPARQL query for later use (Wikidata timeout risk on direct run)
query_path = os.path.join(DEST, "wikidata_religious_buildings.sparql")
with open(query_path, 'w', encoding='utf-8') as f:
    f.write(sparql_query.strip())
print(f"  SAVED: wikidata_religious_buildings.sparql (SPARQL query for 500K religious buildings)")

# ============================================================
# SUMMARY
# ============================================================
print()
print("=" * 60)
print("DOWNLOAD COMPLETE")
print("=" * 60)

total_size = 0
file_count = 0
for f in sorted(os.listdir(DEST)):
    fpath = os.path.join(DEST, f)
    if os.path.isfile(fpath):
        size_mb = os.path.getsize(fpath) / (1024 * 1024)
        total_size += size_mb
        file_count += 1
        print(f"  {size_mb:8.1f} MB  {f}")

print(f"\n  {file_count} files, {total_size:.1f} MB total")
print(f"  Location: {DEST}")

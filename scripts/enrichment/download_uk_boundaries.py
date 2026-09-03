#!/usr/bin/env python3
"""
Download UK census geography boundaries.
Sources: ONS Open Geography Portal
Downloads to data/uk_boundaries/
"""
import urllib.request, zipfile, os
from pathlib import Path

DATA_DIR = Path(r"E:\grid\data\uk_boundaries")
DATA_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOADS = {
    # LSOA 2021 (England+Wales) — GeoJSON from ONS
    "lsoa_2021": {
        "url": "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Lower_layer_Super_Output_Areas_December_2021_Boundaries_EW_BGC_V3/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson",
        "file": "LSOA_2021_EW.geojson",
        "desc": "LSOA 2021 (England+Wales) — GeoJSON via ArcGIS"
    },
    # Westminster constituencies July 2024
    "westminster_2024": {
        "url": "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Westminster_Parliamentary_Constituencies_July_2024_Boundaries_UK_BUC_2/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson",
        "file": "Westminster_2024_UK.geojson",
        "desc": "Westminster constituencies July 2024 — GeoJSON"
    },
}

for key, info in DOWNLOADS.items():
    dest = DATA_DIR / info["file"]
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"✅ Already downloaded: {info['file']} ({dest.stat().st_size/1024/1024:.1f}MB)")
        continue
    print(f"Downloading {info['desc']}...")
    try:
        urllib.request.urlretrieve(info["url"], dest)
        size_mb = dest.stat().st_size / 1024 / 1024
        print(f"  ✅ {size_mb:.1f}MB — {info['file']}")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        # Try shapefile fallback
        zip_dest = DATA_DIR / f"{key}.zip"
        shp_url = info["url"].replace(".gpkg", ".zip")
        try:
            urllib.request.urlretrieve(shp_url, zip_dest)
            print(f"  Shapefile fallback: {zip_dest.stat().st_size/1024/1024:.1f}MB")
        except:
            print(f"  Shapefile fallback also failed")

print("\nDone.")

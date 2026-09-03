#!/usr/bin/env python3
"""
Download the GoodLands Global Diocesan Boundaries v2.0 (2019) as GeoJSON.

Source: ArcGIS Feature Server at
  https://services3.arcgis.com/I88u8wDux7Kis2GZ/arcgis/rest/services/Diocesan_Boundaries/FeatureServer/0

License: CC-BY-ND-4.0 (attribution required, no derivatives)
  For point-in-polygon spatial tagging this is acceptable — we are not modifying the polygons.

Output: data/goodlands_diocesan_boundaries.geojson
"""

import requests
import json
import os
import time

BASE_URL = (
    "https://services3.arcgis.com/I88u8wDux7Kis2GZ/arcgis/rest/services/"
    "Diocesan_Boundaries/FeatureServer/0/query"
)
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                           "data", "goodlands_diocesan_boundaries.geojson")

MAX_RECORDS = 2000  # server-imposed limit
OUT_FIELDS = "OBJECTID,Name,LatinName,DioType,MetroKey,Region,CountryKey,RiteKey,SquareMiles,SquareKM,Population,Vacant,RegionKey"
SPATIAL_REF = 4326  # WGS84 output

def query_batch(offset):
    """Query one batch of features and return GeoJSON response."""
    params = {
        "where": "1=1",
        "outFields": OUT_FIELDS,
        "outSR": str(SPATIAL_REF),
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": MAX_RECORDS,
    }
    resp = requests.get(BASE_URL, params=params, timeout=120)
    resp.raise_for_status()
    return resp.json()

def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    # Get total count
    count_params = {"where": "1=1", "returnCountOnly": "true", "f": "json"}
    count_resp = requests.get(BASE_URL, params=count_params)
    total = count_resp.json()["count"]
    print(f"Total features: {total}")
    
    all_features = []
    offset = 0
    
    while offset < total:
        print(f"Fetching offset {offset}...", end=" ", flush=True)
        gj = query_batch(offset)
        features = gj.get("features", [])
        all_features.extend(features)
        print(f"got {len(features)} features ({len(all_features)}/{total})")
        offset += MAX_RECORDS
        time.sleep(0.5)  # be gentle
    
    # Build output GeoJSON
    out_gj = {
        "type": "FeatureCollection",
        "features": all_features,
        "metadata": {
            "source": "GoodLands Inc. / CGISC Catholic GeoHub",
            "dataset": "Diocesean Boundaries of the Catholic Church v2.0 (2019)",
            "citation": "Burhans, M., Bell, J., Burhans, D., et al. 'Diocesean Boundaries of the Catholic Church' [Feature Layer]. ~1:3M. Version 2.0. Redlands, CA, USA, New Haven, USA, MO: GoodLands Inc., Environmental Systems Research Institute, Inc., 2019.",
            "license": "CC-BY-ND-4.0",
            "download_url": BASE_URL,
            "crs": "EPSG:4326",
            "feature_count": len(all_features),
            "download_date": time.strftime("%Y-%m-%d"),
        }
    }
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out_gj, f, ensure_ascii=False)
    
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nDone! Wrote {len(all_features)} features to:")
    print(f"  {OUTPUT_PATH}")
    print(f"  ({file_size / 1024 / 1024:.1f} MB)")

if __name__ == "__main__":
    main()

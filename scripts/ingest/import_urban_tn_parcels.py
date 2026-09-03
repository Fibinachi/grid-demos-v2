"""
Import religious parcel data from missing urban TN counties.

Counties to import:
  - Davidson (Nashville) — data.nashville.gov
  - Shelby (Memphis) — data.shelbycountytn.gov
  - Knox (Knoxville) — data.knoxcountytn.gov
  - Hamilton (Chattanooga) — data.hamiltontn.gov

Each county has its own data portal. This script downloads, filters,
and merges religious parcels into the TN parcels DB.
"""
import requests, csv, json, sys, os, sqlite3, re, io, time
from datetime import datetime, timezone
from collections import defaultdict

TN_DB = 'data/tn_parcels/tn_religious_parcels.db'
DRY_RUN = '--dry-run' in sys.argv
CHUNK = 500

# ================================================================
# County data sources
# ================================================================
COUNTIES = {
    'Davidson': {
        'name': 'davidson',
        'portal': 'data.nashville.gov',
        'api_base': 'https://data.nashville.gov/api',
        # Parcel dataset - need to find the right ID
        'dataset_ids': [],  # Will be discovered
        'search_terms': ['parcel', 'property', 'assessment', 'tax'],
        'exempt_col': None,  # Will be discovered
    },
    'Shelby': {
        'name': 'shelby',
        'portal': 'data.shelbycountytn.gov',
        'api_base': 'https://data.shelbycountytn.gov/api',
        'dataset_ids': [],
    },
}

def find_parcel_datasets(portal_url, api_base, search_terms):
    """Search a Socrata portal for parcel-related datasets."""
    found = []
    for term in search_terms:
        try:
            url = f"{api_base}/catalog/v1?q={term}&limit=20"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                results = data.get('results', [])
                for item in results:
                    res = item.get('resource', {})
                    name = res.get('name', '')
                    rid = res.get('id', '')
                    rtype = res.get('type', '')
                    # Check if it looks like a parcel dataset
                    name_lower = name.lower()
                    if any(w in name_lower for w in ['parcel', 'property', 'tax', 'assessment']) \
                       and rtype in ['dataset', 'shapefile', 'geojson']:
                        found.append({'id': rid, 'name': name, 'type': rtype, 'portal': portal_url})
            print(f"    {term}: found {len(results)} results")
        except Exception as e:
            print(f"    {term}: ERROR {e}")
    return found

def explore_dataset(api_base, dataset_id, limit=5):
    """Preview a dataset to understand its schema."""
    try:
        # Try SODA API
        url = f"{api_base}/id/{dataset_id}.json?$limit={limit}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data:
                print(f"    Sample: {json.dumps(data[0], indent=2)[:1000]}")
                return data[0].keys()
    except Exception as e:
        pass
    
    # Try CSV export
    try:
        url = f"{api_base}/id/{dataset_id}.csv?$limit={limit}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            reader = csv.DictReader(io.StringIO(r.text))
            for row in reader:
                print(f"    CSV Sample: {dict(list(row.items())[:15])}")
                return row.keys()
    except Exception as e:
        pass
    
    return []

# ================================================================
# Phase 1: Discover datasets on each portal
# ================================================================
print("=" * 70)
print("IMPORT URBAN TN PARCELS — PHASE 1: DISCOVERY")
print("=" * 70)

for county_name, info in COUNTIES.items():
    print(f"\n--- {county_name} County ---")
    print(f"  Portal: {info['portal']}")
    
    datasets = find_parcel_datasets(
        info['portal'], info['api_base'], info.get('search_terms', ['parcel', 'property'])
    )
    
    print(f"  Found {len(datasets)} parcel-related datasets:")
    for ds in datasets:
        print(f"    {ds['id']:15s} {ds['type']:10s} {ds['name'][:60]}")
    
    # Explore the most promising one
    if datasets:
        print(f"\n  Exploring most promising dataset...")
        cols = explore_dataset(info['api_base'], datasets[0]['id'])
        print(f"  Columns: {list(cols)[:20] if cols else 'none'}")

# For now, let's also check if there's a simpler approach:
# Many counties have ArcGIS REST endpoints we can query directly
print("\n\n=== Checking ArcGIS REST endpoints ===")
arcgis_urls = [
    # Davidson County parcels (ArcGIS)
    'https://maps.nashville.gov/arcgis/rest/services/Property/Parcels_Map/FeatureServer/0/query',
    # Shelby County parcels
    'https://services1.arcgis.com/Fv0FPwQX0N8jVE7G/arcgis/rest/services/Parcels/FeatureServer/0/query',
]

for url in arcgis_urls:
    try:
        r = requests.get(url + '?where=1%3D1&returnCountOnly=true&f=json', timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = data.get('count', data.get('properties', {}).get('count', '?'))
            print(f"  {url[:60]:60s} → count={count}")
        else:
            print(f"  {url[:60]:60s} → HTTP {r.status_code}")
    except Exception as e:
        print(f"  {url[:60]:60s} → ERROR {e}")

print("\nPhase 1 complete. Results will guide Phase 2 download.")
print(f"\nNext steps after discovery:")
print(f"  1. Download parcel data from each county's API")
print(f"  2. Filter for religious exemptions (property class codes)")
print(f"  3. Merge into tn_religious_parcels.db")
print(f"  4. Dedup against existing churches.db")

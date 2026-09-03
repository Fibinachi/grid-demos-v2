"""Scrape all WOF dataset metadata from HDX CKAN API and build BQ ingestion plan."""
import json, urllib.request, os, sys, zipfile, tempfile, shutil
from urllib.parse import urlparse

# Step 1: Get all WOF datasets via CKAN API (with pagination)
print("=== Fetching WOF organization metadata from CKAN API ===")

# Use package_search with pagination instead (org show has cap issues)
all_packages = []
start = 0
limit = 100

print("Fetching via package_search with pagination...")
while True:
    url = f"https://data.humdata.org/api/3/action/package_search?fq=organization:wof&rows={limit}&start={start}&sort=name+asc"
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read())
    
    results = data["result"]["results"]
    total = data["result"]["count"]
    
    all_packages.extend(results)
    print(f"  Fetched {len(results)} (offset={start}, total={total})")
    
    if len(all_packages) >= total:
        break
    start += limit

print(f"Total datasets: {len(all_packages)}")

# Extract key metadata for each dataset
datasets = []
for pkg in all_packages:
    iso3 = None
    download_url = None
    resource_size = None
    
    # Extract ISO3 from name pattern: whosonfirst-data-admin-{iso3}
    name = pkg["name"]
    if name.startswith("whosonfirst-data-admin-"):
        iso3 = name.replace("whosonfirst-data-admin-", "")
    
    # Get first resource (the SHP download)
    if pkg.get("resources"):
        res = pkg["resources"][0]
        download_url = res.get("url")
        resource_size = res.get("size")
    
    datasets.append({
        "name": name,
        "title": pkg.get("title", ""),
        "iso3": iso3,
        "download_url": download_url,
        "size_bytes": resource_size,
        "num_resources": len(pkg.get("resources", [])),
        "metadata_modified": pkg.get("metadata_modified", ""),
    })

# Sort by iso3
datasets.sort(key=lambda d: d["iso3"] or "")

# Print summary
print(f"\n=== WOF Dataset Summary ===")
total_size = sum(d["size_bytes"] or 0 for d in datasets)
print(f"Valid ISO3 codes: {sum(1 for d in datasets if d['iso3'])}")
print(f"Total download size: {total_size/1024/1024/1024:.1f} GB")
print(f"Datasets with URLs: {sum(1 for d in datasets if d['download_url'])}")

# Print top 20 largest
print(f"\n=== Top 20 Largest Countries ===")
by_size = sorted([d for d in datasets if d['size_bytes']], key=lambda d: -d['size_bytes'])
print(f"{'ISO3':6s} {'Size (MB)':>10s} {'Name':40s}")
print("-"*60)
for d in by_size[:20]:
    print(f"{d['iso3']:6s} {d['size_bytes']/1024/1024:>8.1f}MB  {d['title'][:40]}")

# Print number of small vs large
small = sum(1 for d in datasets if d['size_bytes'] and d['size_bytes'] < 10*1024*1024)
medium = sum(1 for d in datasets if d['size_bytes'] and 10*1024*1024 <= d['size_bytes'] < 100*1024*1024)
large = sum(1 for d in datasets if d['size_bytes'] and d['size_bytes'] >= 100*1024*1024)
huge = sum(1 for d in datasets if d['size_bytes'] and d['size_bytes'] >= 500*1024*1024)
print(f"\nSize distribution:")
print(f"  < 10MB:    {small}")
print(f"  10-100MB:  {medium}")
print(f"  100-500MB: {large}")
print(f"  500MB+:    {huge}")

# Save the dataset list as JSON for later use
with open("data/raw/wof_datasets.json", "w") as f:
    json.dump(datasets, f, indent=2)
print(f"\nSaved dataset list to data/raw/wof_datasets.json")

# Print a few sample download URLs
print(f"\n=== Sample Download URLs ===")
for d in by_size[:5]:
    print(f"  {d['iso3']}: {d['download_url']}")

"""Download a small WOF SHP and inspect its structure."""
import json, urllib.request, os, zipfile, tempfile, shutil

# Download a small country (Singapore - likely tiny)
url = "https://data.geocode.earth/wof/dist/shapefile/whosonfirst-data-admin-sg-latest.zip"
local_zip = "data/raw/wof_sg_test.zip"

print(f"Downloading Singapore WOF...")
urllib.request.urlretrieve(url, local_zip)
size_mb = os.path.getsize(local_zip) / 1024 / 1024
print(f"  Downloaded {size_mb:.1f} MB")

# Extract and list contents
extract_dir = "data/raw/wof_sg_test"
os.makedirs(extract_dir, exist_ok=True)

with zipfile.ZipFile(local_zip) as z:
    z.extractall(extract_dir)

print(f"\n=== Files in {extract_dir} ===")
for f in sorted(os.listdir(extract_dir)):
    fsize = os.path.getsize(os.path.join(extract_dir, f))
    print(f"  {f:50s} {fsize/1024:>8.1f} KB")

# Try to read shapefiles with geopandas
print(f"\n=== Shapefile layers ===")
import geopandas as gpd
import glob

shp_files = glob.glob(os.path.join(extract_dir, "*.shp"))
for shp in shp_files:
    name = os.path.basename(shp)
    try:
        gdf = gpd.read_file(shp)
        print(f"\n  {name}:")
        print(f"    Rows: {len(gdf)}")
        print(f"    Columns: {list(gdf.columns)}")
        print(f"    CRS: {gdf.crs}")
        # Show a few sample rows
        for _, row in gdf.head(3).iterrows():
            props = {k: v for k, v in row.items() if k != 'geometry'}
            print(f"    Sample: {props}")
    except Exception as e:
        print(f"  {name}: ERROR - {e}")

print(f"\nDone.")

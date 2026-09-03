"""
Download statewide property tax/parcel data for NY, NJ, WA, MA, MD, WI.
These are bulk statewide datasets — single downloads covering all counties.
"""
import urllib.request
import os
import json
import time

DEST = r"E:\grid\data\sources"
os.makedirs(DEST, exist_ok=True)

def download(url, filename, desc, subdir=None):
    d = os.path.join(DEST, subdir) if subdir else DEST
    os.makedirs(d, exist_ok=True)
    outpath = os.path.join(d, filename)
    if os.path.exists(outpath):
        sz = os.path.getsize(outpath) / (1024*1024)
        print(f"  SKIP ({sz:.0f}MB): {desc}")
        return outpath
    print(f"  DOWNLOAD: {desc} ...", flush=True)
    try:
        urllib.request.urlretrieve(url, outpath)
        sz = os.path.getsize(outpath) / (1024*1024)
        print(f"  OK ({sz:.0f}MB): {filename}", flush=True)
        return outpath
    except Exception as e:
        print(f"  FAIL: {e}", flush=True)
        if os.path.exists(outpath):
            os.remove(outpath)
        return None

def try_arcgis_downloads(item_id, portal, name, subdir):
    """Try common ArcGIS Hub download formats for a dataset."""
    base = f"https://{portal}/api/download/v1/items/{item_id}"
    formats = [
        ("shapefile", ".zip"),
        ("geojson", ".geojson"),
        ("csv", ".csv"),
        ("filegdb", ".gdb.zip"),
    ]
    for fmt, ext in formats:
        url = f"{base}/{fmt}"
        filename = f"{name}{ext}"
        result = download(url, filename, f"{name} ({fmt})", subdir)
        if result:
            return result
    return None

# ================================================================
# 1. NEW YORK — NYS Tax Parcels Public (2025, statewide, single download)
#    Portal: data.gis.ny.gov
# ================================================================
print("=" * 60)
print("1. NEW YORK — Statewide Tax Parcels")
print("=" * 60)

# NY item ID from the dataset page: sharegisny::nys-tax-parcels-public
# Try ArcGIS Hub API to get download links
ny_item = "b5acd52aace0498f8953f583c5d1e619"
try_arcgis_downloads(ny_item, "data.gis.ny.gov", "ny_tax_parcels_2025", "NY_parcels")

# Also try the direct NYS GIS Clearinghouse download
download(
    "https://data.gis.ny.gov/datasets/sharegisny::nys-tax-parcels-public.geojson",
    "ny_tax_parcels.geojson",
    "NY Tax Parcels (direct GeoJSON)",
    "NY_parcels"
)

# ================================================================
# 2. NEW JERSEY — MOD-IV Tax List + Parcels
#    Portal: njogis-newjersey.opendata.arcgis.com
# ================================================================
print()
print("=" * 60)
print("2. NEW JERSEY — MOD-IV Tax List & Parcels")
print("=" * 60)

nj_id = "406cf6860390467d9f328ed19daa359d"
try_arcgis_downloads(nj_id, "njogis-newjersey.opendata.arcgis.com", "nj_mod4_parcels", "NJ_parcels")

# Also try the NJOGIS direct download page
download(
    "https://njogis-newjersey.opendata.arcgis.com/datasets/406cf6860390467d9f328ed19daa359d_0.geojson",
    "nj_parcels.geojson",
    "NJ Parcels (direct GeoJSON)",
    "NJ_parcels"
)

# ================================================================
# 3. WASHINGTON — Current Parcels (statewide, GDB)
#    Portal: geo.wa.gov
# ================================================================
print()
print("=" * 60)
print("3. WASHINGTON — Current Parcels")
print("=" * 60)

# WA DOT Current Parcels
wa_id = "6d9d7e3e6b5a4c32b8f9a1c5e7d3f2a0"  # Need correct ID
# Try the geo.wa.gov portal
download(
    "https://geo.wa.gov/datasets/WADOT::current-parcels.geojson",
    "wa_current_parcels.geojson",
    "WA Current Parcels (GeoJSON)",
    "WA_parcels"
)

# Also try known WA parcel data endpoint
download(
    "https://services6.arcgis.com/rWgPxEaLomdfVkLw/arcgis/rest/services/WA_Statewide_Parcels/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson&resultRecordCount=1000",
    "wa_parcels_sample.geojson",
    "WA Parcels (FeatureServer sample)",
    "WA_parcels"
)

# ================================================================
# 4. MASSACHUSETTS — MassGIS Property Tax Parcels
#    Portal: Mass.gov (direct download)
# ================================================================
print()
print("=" * 60)
print("4. MASSACHUSETTS — MassGIS Tax Parcels")
print("=" * 60)

# MassGIS provides a single ZIP with all municipalities
download(
    "https://download.massgis.digital.mass.gov/shapefiles/statewide/l3_parcels_sde.zip",
    "ma_l3_parcels_sde.zip",
    "MA MassGIS Level 3 Parcels (statewide SDE)",
    "MA_parcels"
)

# Fallback: try the standardized assessor parcels
download(
    "https://download.massgis.digital.mass.gov/shapefiles/statewide/parcels_sde.zip",
    "ma_parcels_sde.zip",
    "MA MassGIS Parcels (statewide)",
    "MA_parcels"
)

# ================================================================
# 5. MARYLAND — SDAT Real Property Assessments
#    Portal: opendata.maryland.gov (Socrata)
# ================================================================
print()
print("=" * 60)
print("5. MARYLAND — SDAT Property Assessments")
print("=" * 60)

# Socrata API CSV export — statewide dataset
download(
    "https://opendata.maryland.gov/api/views/ed4q-f8tm/rows.csv?accessType=DOWNLOAD",
    "md_real_property_assessments.csv",
    "MD SDAT Real Property Assessments (CSV)",
    "MD_parcels"
)

# Also try the smaller fields reference + main dataset with limit
download(
    "https://opendata.maryland.gov/api/views/ed4q-f8tm/rows.csv?accessType=DOWNLOAD&$limit=100000",
    "md_property_sample_100k.csv",
    "MD Property Assessments (100K sample)",
    "MD_parcels"
)

# ================================================================
# 6. WISCONSIN — Statewide Parcel Map
#    Portal: maps.sco.wisc.edu
# ================================================================
print()
print("=" * 60)
print("6. WISCONSIN — Statewide Parcel Map")
print("=" * 60)

# Wisconsin SCO provides statewide parcel data
# Try the download portal
download(
    "https://maps.sco.wisc.edu/Parcels/Download",
    "wi_parcels_download_page.html",
    "WI Parcel Download page",
    "WI_parcels"
)

# Try the WI state ArcGIS REST endpoint
download(
    "https://maps.sco.wisc.edu/arcgis/rest/services/Parcels/Statewide_V8/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson&resultRecordCount=1000",
    "wi_parcels_sample.geojson",
    "WI Parcels (sample)",
    "WI_parcels"
)

# ================================================================
# SUMMARY
# ================================================================
print()
print("=" * 60)
print("DOWNLOAD COMPLETE")
print("=" * 60)

grand_total = 0
for subdir in sorted(os.listdir(DEST)):
    d = os.path.join(DEST, subdir)
    if os.path.isdir(d):
        sub_size = 0
        file_count = 0
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            if os.path.isfile(fp):
                sz = os.path.getsize(fp)
                sub_size += sz
                file_count += 1
        if file_count > 0:
            grand_total += sub_size
            print(f"  {subdir:20s}  {file_count:2d} files  {sub_size/(1024*1024):8.1f} MB")

print(f"\n  Total: {grand_total/(1024*1024):.1f} MB in {DEST}")

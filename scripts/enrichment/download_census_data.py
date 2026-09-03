"""Download ACS/Food Access/PLACES data and enrich church DB by county FIPS"""
import csv, io, json, os, sqlite3, urllib.request, urllib.error, ssl, gzip
from datetime import datetime

DB = r'E:\grid\churches.db'
DATA = r'E:\grid\data\census'
os.makedirs(DATA, exist_ok=True)

ctx = ssl.create_default_context()

def dl(url, path):
    """Download if not cached."""
    if os.path.exists(path):
        sz = os.path.getsize(path)
        print(f"  Cached: {path} ({sz:,} bytes)")
        return
    print(f"  Downloading {url[:80]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            data = r.read()
            with open(path, 'wb') as f:
                f.write(data)
        print(f"    -> {path} ({len(data):,} bytes)")
    except Exception as e:
        print(f"    FAILED: {e}")

print("=" * 60)
print("Downloading Census/ACS/Food/Health Data")
print("=" * 60)

# ── 1. ACS 5-year 2023 — county-level key demographics ──
# Census API: variables for median income, poverty, education, population
# No API key needed for small queries, but better with key
# We'll query by state for manageable chunks

print("\n[1] ACS 5-year 2023 (County-level)...")

# Variables we want (ACS 5-year 2023)
VARS = [
    "NAME",                    # County name
    "B01001_001E",             # Total population
    "B19013_001E",             # Median household income
    "B17001_001E",             # Total poverty universe
    "B17001_002E",             # Income below poverty level
    "B15003_001E",             # Total population 25+ (education universe)
    "B15003_022E",             # Bachelor's degree
    "B15003_023E",             # Master's degree
    "B15003_024E",             # Professional degree
    "B15003_025E",             # Doctorate degree
    "B23025_001E",             # Total employment universe
    "B23025_003E",             # Employed
    "B23025_005E",             # Unemployed
    "B25072_001E",             # Median gross rent
    "B25077_001E",             # Median home value
    "B01002_001E",             # Median age
    "B02001_001E",             # Total race population
    "B02001_002E",             # White alone
    "B02001_003E",             # Black or African American alone
    "B02001_004E",             # American Indian / Alaska Native
    "B02001_005E",             # Asian alone
    "B02001_006E",             # Native Hawaiian / Pacific Islander
    "B03003_001E",             # Hispanic/Latino population
    "B03003_003E",             # Hispanic or Latino
    "B05001_001E",             # Total citizenship
    "B05001_006E",             # Not a US citizen
]

acs_csv = os.path.join(DATA, "acs_county_2023.csv")
if not os.path.exists(acs_csv):
    # Query county-level data for all states + DC + PR
    all_rows = []
    # Try API without key first
    api = "https://api.census.gov/data/2023/acs/acs5"
    params = "get=" + ",".join(VARS)
    params += "&for=county:*"
    
    url = f"{api}?{params}"
    print(f"  Querying {url[:80]}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            data = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f"  API query failed: {e}")
        print("  Trying with census key if available...")
        # Check for census key file
        key_file = os.path.join(os.path.dirname(DB), "census_key.txt")
        if os.path.exists(key_file):
            key = open(key_file).read().strip()
            url = f"{api}?{params}&key={key}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "GrantWizard/1.0"})
                with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
                    data = json.loads(r.read().decode('utf-8'))
            except Exception as e2:
                print(f"  With key also failed: {e2}")
                data = None
        else:
            data = None
    
    if data:
        with open(acs_csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            for row in data:
                w.writerow(row)
        print(f"    Wrote {len(data)-1:,} rows to {acs_csv}")
    else:
        print("    Using fallback: download pre-packaged ACS data")
        # Fallback: download from census ftp
        acs_url = "https://www2.census.gov/programs-surveys/acs/summary_file/2023/table-based-SF/data/ACSDP5y2023/ACSDP5y2023_county.csv"
        dl(acs_url, acs_csv)
else:
    print(f"  Cached: {acs_csv}")

# ── 2. USDA Food Access Atlas ──

print("\n[2] USDA Food Access Atlas...")
food_csv = os.path.join(DATA, "food_access_atlas.csv")
food_url = "https://www.ers.usda.gov/webdocs/DataFiles/80591/FoodAccessResearchAtlas2023.csv"
dl(food_url, food_csv)

# ── 3. CDC PLACES (County-level) ──

print("\n[3] CDC PLACES (County-level health data)...")
cdc_csv = os.path.join(DATA, "cdc_places_county.csv")
# CDC PLACES county-level data from chronicdata.cdc.gov
cdc_url = "https://chronicdata.cdc.gov/api/views/swc5-6bwp/rows.csv?accessType=DOWNLOAD"
dl(cdc_url, cdc_csv)

print("\nAll downloads complete!")
print(f"\nFiles:")
for f in os.listdir(DATA):
    sz = os.path.getsize(os.path.join(DATA, f))
    print(f"  {f}: {sz:,} bytes")

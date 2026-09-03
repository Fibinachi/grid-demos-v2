"""Download ACS/USDA/CDC with Census API key, upload to S3"""
import csv, json, os, urllib.request, subprocess

KEY = os.environ.get("CENSUS_API_KEY", "2159d6ade3d596371c9333d6118d1ef2f9342cf4")
DATA = r"E:\grid\data\census"
UA = "Mozilla/5.0"
os.makedirs(DATA, exist_ok=True)

def dl_json(name, url):
    p = os.path.join(DATA, name)
    if os.path.exists(p): print(f"  Cached: {name}"); return True
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"application/json"})
        d = json.loads(urllib.request.urlopen(r, timeout=120).read().decode("utf-8-sig"))
        with open(p, 'w') as f: json.dump(d, f)
        print(f"  Downloaded: {name} ({len(d):,} rows)"); return True
    except Exception as e:
        print(f"  FAILED {name}: {e}"); return False

def dl_csv(name, url):
    p = os.path.join(DATA, name)
    if os.path.exists(p): print(f"  Cached: {name}"); return True
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(r, timeout=120).read()
        with open(p, 'wb') as f: f.write(raw)
        print(f"  Downloaded: {name} ({len(raw):,} bytes)"); return True
    except Exception as e:
        print(f"  FAILED {name}: {e}"); return False

print("="*60)
print("ACS/USDA/CDC Download -> S3")
print("="*60)

print("\n[1] ACS 5-year 2023 County...")
v = ",".join(["NAME","B01001_001E","B19013_001E","B17001_001E","B17001_002E",
    "B15003_022E","B15003_023E","B15003_024E","B15003_025E",
    "B23025_003E","B23025_005E","B25077_001E","B01002_001E",
    "B02001_002E","B02001_003E","B02001_004E","B02001_005E","B03003_003E"])
dl_json("acs_2023_county.json", f"https://api.census.gov/data/2023/acs/acs5?get={v}&for=county:*&key={KEY}")

print("\n[2] USDA Food Access Atlas...")
dl_csv("food_access_2023.csv", "https://www.ers.usda.gov/webdocs/DataFiles/80591/FoodAccessResearchAtlas2023.csv")

print("\n[3] CDC PLACES County...")
dl_csv("cdc_places_2024.csv", "https://data.cdc.gov/api/views/7xgy-y3pp/rows.csv?accessType=DOWNLOAD")

print("\n[4] Uploading to S3...")
bucket = "grantwizard-census-data"
subprocess.run(["aws","s3","mb",f"s3://{bucket}","--region","us-east-1"], capture_output=True)

for fn in sorted(os.listdir(DATA)):
    fp = os.path.join(DATA, fn)
    if os.path.isfile(fp) and os.path.getsize(fp) > 0:
        r = subprocess.run(["aws","s3","cp",fp,f"s3://{bucket}/{fn}","--region","us-east-1"], capture_output=True, text=True)
        print(f"  {'OK' if r.returncode==0 else 'FAIL'}: {fn}")

print(f"\nFiles in s3://{bucket}/:")
subprocess.run(["aws","s3","ls",f"s3://{bucket}/","--region","us-east-1"])

"""Test Census API speed"""
import urllib.request, json, time

KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"
zips = ["92630","10001","77001","60606","90001","33101","20001","75201","85001","02101"]

t0 = time.time()
success = 0
for z in zips:
    url = f"https://api.census.gov/data/2022/acs/acs5/subject?get=NAME,S0101_C01_001E&for=zip+code+tabulation+area:{z}&key={KEY}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read().decode())
        success += 1
    except Exception as e:
        print(f"  {z}: {e}")

elapsed = time.time() - t0
print(f"{len(zips)} requests in {elapsed:.1f}s ({len(zips)/elapsed:.1f}/s), {success} ok")

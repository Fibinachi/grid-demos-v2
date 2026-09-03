"""Test Census API key"""
import urllib.request, json, os

KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"
os.environ["CENSUS_API_KEY"] = KEY

# Test with a ZIP code
url = f"https://api.census.gov/data/2022/acs/acs5?get=NAME,B19013_001E,B01001_001E,B17001_002E&for=zip+code+tabulation+area:92630&key={KEY}"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req, timeout=10)
data = json.loads(resp.read().decode())

print("=== Census API Test ===")
print(f"ZIP 92630 - Lake Forest, CA")
print(f"  Name: {data[1][0]}")
print(f"  Median Income: ${int(data[1][1]):,}")
print(f"  Population: {int(data[1][2]):,}")
print(f"  Poverty Count: {int(data[1][3]):,}")
print(f"  API Key: {KEY[:10]}...{KEY[-4:]}")
print("✅ Census API working!")

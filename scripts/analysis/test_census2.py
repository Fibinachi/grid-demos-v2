"""Debug Census API URL format"""
import urllib.request, json

url = "https://api.census.gov/data/2022/acs/acs5?get=NAME,B19013_001E,B01001_001E&for=zip+code+tabulation+area:92630"
print(f"URL: {url}")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        text = resp.read().decode()
        print(f"Response ({len(text)} bytes): {text[:500]}")
except Exception as e:
    print(f"Error: {e}")
    
# Try without zip code specifier - get list of available years/endpoints
try:
    url2 = "https://api.census.gov/data.json"
    req2 = urllib.request.Request(url2, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req2, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    # Find ACS endpoints
    for ds in data.get("dataset", [])[:5]:
        print(f"\nDataset: {ds.get('title','?')} - {ds.get('c_dataset',['?'])[0]}")
except Exception as e:
    print(f"Error2: {e}")

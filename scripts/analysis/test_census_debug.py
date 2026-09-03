"""Debug Census API response"""
import urllib.request, json

KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"
url = f"https://api.census.gov/data/2022/acs/acs5?get=NAME,B19013_001E,B01001_001E&for=zip+code+tabulation+area:92630&key={KEY}"
print(f"URL: {url}")
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req, timeout=10)
text = resp.read().decode()
print(f"Response ({len(text)} bytes):")
print(text[:500])

#!/usr/bin/env python3
"""Test Google Places API with the exposed Salvation Army key."""
import urllib.request, json, os

KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
if not KEY:
    raise ValueError("GOOGLE_PLACES_API_KEY environment variable is required")

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

# Test Text Search
print("=== TEXT SEARCH (Columbia SC) ===")
d = fetch(f"https://maps.googleapis.com/maps/api/place/textsearch/json?query=Salvation+Army+Columbia+SC&key={KEY}")
print(f"Status: {d.get('status')}")
if d.get("status") == "OK":
    print(f"Results: {len(d.get('results', []))}")
    for r in d.get("results", [])[:10]:
        print(f"  {r['name'][:50]:50s} {r.get('formatted_address','')[:60]}")
else:
    print(f"Error: {d.get('error', d.get('status', d))}")

# Test Nearby Search
print("\n=== NEARBY SEARCH (Columbia SC) ===")
d2 = fetch(f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=34.0007,-81.0348&radius=50000&keyword=Salvation+Army&key={KEY}")
print(f"Status: {d2.get('status')}")
if d2.get("status") == "OK":
    print(f"Results: {len(d2.get('results', []))}")
    for r in d2.get("results", [])[:10]:
        print(f"  {r['name'][:50]:50s} {r.get('vicinity','')[:60]}")
else:
    print(f"Error: {d2.get('error', d2.get('status', d2)[:200])}")

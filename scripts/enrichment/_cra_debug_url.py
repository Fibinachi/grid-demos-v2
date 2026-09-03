import urllib.request, time

RESOURCE_ID = "5e58be8c-8d58-4b99-b643-88852ae2f98f"
url = f"https://open.canada.ca/data/api/action/datastore_search?resource_id={RESOURCE_ID}&limit=1"
print(f"URL: {url}")

time.sleep(2)
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read()
    print(f"Status: {resp.status}")
    print(f"Headers: {dict(resp.headers)}")
    print(f"Body (first 500): {raw[:500]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

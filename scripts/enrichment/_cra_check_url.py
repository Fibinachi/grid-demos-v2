import urllib.request
import time, os

URLS = [
    # T3010 registered charity data by province (full XML)
    "https://apps.cra-arc.gc.ca/ebci/hacc/ceaf/dsrd/xlnt/p/bScArs?request_locale=en_CA&pkgFlNm=T3010-1_ALL_BY_PROVINCE_1.zip",
    # Alternative: full charities listing CSV 
    "https://www.canada.ca/content/dam/cra-arc/serv-info/charities/charities.zip",
]

for url in URLS:
    print(f"\nTesting: {url[:80]}...")
    time.sleep(3)  # rate limit
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        ct = resp.headers.get("Content-Type", "?")
        cl = resp.headers.get("Content-Length", "?")
        print(f"  OK: Content-Type={ct}, Content-Length={cl}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

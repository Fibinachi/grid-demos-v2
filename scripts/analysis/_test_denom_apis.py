"""Debug denom APIs from EC2"""
import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def test(name, url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(r, timeout=10) as f:
            data = f.read()
            print(f"{name}: {len(data)} bytes, status={f.getcode()}")
            print(data[:500])
    except Exception as e:
        print(f"{name}: ERROR: {e}")

test("SBC", "https://churches.sbc.net/api/churches?page=1&per_page=5")
test("LCMS", "https://locator.lcms.org/api/v1/congregations?limit=5")
test("Episcopal", "https://api.episcopalassetmap.org/api/v1/places?limit=5&type=church")

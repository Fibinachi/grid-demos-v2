"""Check if Shepherd's Stream is in Common Crawl."""
import urllib.request, json

def check_cc(query, label):
    url = f"https://index.commoncrawl.org/CC-MAIN-2025-18-index?url={query}&output=json&limit=10"
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode()
        lines = [l for l in data.strip().split("\n") if l.strip()]
        print(f"{label}: {len(lines)} results")
        for l in lines[:3]:
            j = json.loads(l)
            url_val = j.get("url", "?")[:75]
            status = j.get("status", "?")
            print(f"  [{status}] {url_val}")
        return len(lines)
    except Exception as e:
        print(f"{label}: Error - {e}")
        return 0

check_cc("*.shepherdsstream.org/*", "All SS pages")
check_cc("*.shepherdsstream.org/*church*", "SS church dir pages")
check_cc("*.shepherdsstream.org/*arkansas*", "SS Arkansas pages")

# Check a few more crawls for broader coverage
for crawl in ["CC-MAIN-2025-04", "CC-MAIN-2024-42", "CC-MAIN-2024-26"]:
    url = f"https://index.commoncrawl.org/{crawl}-index?url=*.shepherdsstream.org/*&output=json&limit=5"
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode()
        lines = [l for l in data.strip().split("\n") if l.strip()]
        print(f"\n{crawl}: {len(lines)} SS pages")
    except Exception as e:
        print(f"\n{crawl}: Error - {e}")

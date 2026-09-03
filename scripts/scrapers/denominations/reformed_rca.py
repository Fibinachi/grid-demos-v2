"""
RCA Church Scraper — Reformed Church in America
Uses WP Store Locator plugin API at rca.org
"""
import json, time, urllib.request

UA = "Mozilla/5.0 (compatible; GrantWizard/1.0)"

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except:
        return None

def main():
    results = []
    page = 1
    while True:
        data = fetch_json(f"https://www.rca.org/wp-json/wp/v2/wpsl_stores?per_page=100&page={page}")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        for item in data:
            title = item.get("title", {}).get("rendered", "")
            if title:
                results.append({"name": title.strip(), "denomination": "Reformed Church in America"})
        print(json.dumps({"page": page, "count": len(results), "total": "?"}))
        page += 1
        time.sleep(0.3)
    print(json.dumps({"done": True, "total": len(results)}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

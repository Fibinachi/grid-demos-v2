"""
PCA Church Scraper — Presbyterian Church in America
Uses PCA's church directory API at pcaac.org
"""
import json, time, urllib.request, re

UA = "Mozilla/5.0 (compatible; GrantWizard/1.0)"

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except:
        return None

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=15).read())
    except:
        return None

def main():
    results = []
    page = 1
    # Try PCA's church search API
    while True:
        data = fetch_json(f"https://www.pcaac.org/wp-json/wp/v2/church?per_page=100&page={page}")
        if data and isinstance(data, list) and len(data) > 0:
            for item in data:
                title = item.get("title", {}).get("rendered", "")
                if title:
                    results.append({"name": title.strip(), "denomination": "Presbyterian Church in America"})
            page += 1
            time.sleep(0.3)
        else:
            break
    
    if not results:
        # Fallback: try the PCA church search HTML page
        html = fetch("https://www.pcaac.org/church-search/")
        if html:
            churches = re.findall(r'<h[23][^>]*>([^<]+)</h', html)
            for c in churches:
                c = c.strip()
                if c and len(c) > 3:
                    results.append({"name": c, "denomination": "Presbyterian Church in America"})
    
    print(json.dumps({"done": True, "total": len(results)}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

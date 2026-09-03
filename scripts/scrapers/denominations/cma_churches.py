"""
CMA Church Scraper — Christian and Missionary Alliance
Scrapes cmalliance.org church locator
"""
import json, time, urllib.request, re

UA = "Mozilla/5.0 (compatible; GrantWizard/1.0)"

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
    except:
        return None

def main():
    results = []
    # Try church search page
    html = fetch("https://www.cmalliance.org/churches/")
    if html:
        churches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for c in churches:
            c = c.strip()
            if c and len(c) > 3:
                results.append({"name": c, "denomination": "Christian and Missionary Alliance"})
    
    # Try WP API fallback
    if not results:
        import urllib.parse
        for page in [1, 2, 3]:
            try:
                req = urllib.request.Request(
                    f"https://www.cmalliance.org/wp-json/wp/v2/church?per_page=100&page={page}",
                    headers={"User-Agent": UA, "Accept": "application/json"}
                )
                data = json.loads(urllib.request.urlopen(req, timeout=10).read())
                if isinstance(data, list):
                    for item in data:
                        title = item.get("title", {}).get("rendered", "")
                        if title:
                            results.append({"name": title.strip(), "denomination": "Christian and Missionary Alliance"})
            except:
                break
            time.sleep(0.3)
    
    print(json.dumps({"done": True, "total": len(results)}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

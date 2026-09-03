"""
Wesleyan Church Scraper
Scrapes wesleyan.org district websites for church listings
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
    
    # Try the find-a-church page
    html = fetch("https://www.wesleyan.org/find-a-church/")
    if html:
        churches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for c in churches:
            c = c.strip()
            if c and len(c) > 3:
                results.append({"name": c, "denomination": "Wesleyan Church"})
    
    # Try district list page
    html = fetch("https://www.wesleyan.org/about/districts")
    if html:
        districts = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html)
        district_urls = [(url, name) for url, name in districts if "district" in url.lower() or "wesleyan" in url.lower()]
        print(json.dumps({"districts_found": len(district_urls), "note": "Wesleyan has ~22 district websites, each needs separate scraping"}))
    
    print(json.dumps({"done": True, "total": len(results), "note": "Wesleyan find-a-church is JS-rendered with no public API. Try district-level scraping."}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

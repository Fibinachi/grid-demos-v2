"""
UCC Church Scraper — United Church of Christ
Scrapes ucc.org church finder data
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
    # Try conference-level directories (UCC organized by conferences)
    html = fetch("https://www.ucc.org/find-a-church/")
    if html:
        churches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for c in churches:
            c = c.strip()
            if c and len(c) > 3:
                results.append({"name": c, "denomination": "United Church of Christ"})
    
    # Try conferences list
    if not results:
        html = fetch("https://www.ucc.org/about/our-conferences/")
        if html:
            conf_links = re.findall(r'<a[^>]*href="([^"]*conference[^"]*)"[^>]*>([^<]+)</a>', html, re.I)
            print(json.dumps({"conferences_found": len(conf_links), "note": "UCC uses conference-level directories, each conference has its own site"}))
    
    print(json.dumps({"done": True, "total": len(results), "note": "UCC has no central church directory API. Consider scraping individual conference websites."}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

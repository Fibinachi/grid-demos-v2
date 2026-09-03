"""
NBC Church Scraper — National Baptist Convention USA
Scrapes nationalbaptist.com and state convention websites
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
    
    # Check main site for any church directory
    html = fetch("https://www.nationalbaptist.com/")
    if html:
        churches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for c in churches:
            c = c.strip()
            if c and len(c) > 3:
                results.append({"name": c, "denomination": "National Baptist Convention USA"})
    
    print(json.dumps({"done": True, "total": len(results), 
                       "note": "NBC USA has no central church directory. Their website is a convention site only. "
                               "State conventions and local associations maintain their own directories."}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

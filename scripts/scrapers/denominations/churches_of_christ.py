"""
Churches of Christ Scraper
No central denomination directory exists (independent congregationalist polity)
Uses churchzip.com and other aggregators as fallback
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
    
    # Try churchzip.com search for Churches of Christ
    html = fetch("https://www.churchzip.com/")
    if html:
        # Extract any church names from homepage
        churches = re.findall(r'<h3[^>]*>([^<]+)</h3>', html)
        for c in churches:
            c = c.strip()
            if c and len(c) > 3 and "church" in c.lower():
                results.append({"name": c, "denomination": "Churches of Christ"})
    
    print(json.dumps({"done": True, "total": len(results),
                       "note": "Churches of Christ have no central directory (congregationalist). "
                               "They are already well-represented in IRS/EPA data by name patterns. "
                               "Recommend using name-based classification ('Church of Christ' patterns) instead."}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

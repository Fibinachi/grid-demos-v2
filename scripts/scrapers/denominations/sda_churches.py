"""
SDA Church Scraper — Seventh-day Adventist
Uses adventistdirectory.org for church listings
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
    states = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
              "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
              "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
              "VA","WA","WV","WI","WY"]
    
    for state in states:
        html = fetch(f"https://www.adventistdirectory.org/SearchForm.aspx?State={state}")
        if html:
            churches = re.findall(r'<td[^>]*class="[^"]*church[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>', html, re.DOTALL)
            if not churches:
                churches = re.findall(r'<a[^>]*href="[^"]*organization[^"]*"[^>]*>([^<]+)</a>', html)
            for c in churches:
                c = c.strip()
                if c and len(c) > 3:
                    results.append({"name": c, "denomination": "Seventh-day Adventist"})
        time.sleep(0.5)
    
    print(json.dumps({"done": True, "total": len(results)}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

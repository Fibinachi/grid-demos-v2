"""
JW Church Scraper — Jehovah's Witnesses congregations
Uses JW Hub meeting finder API
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
    # Try JW Hub API for meeting locations
    endpoints = [
        "https://hub.jw.org/api/public/meeting-search?countryCode=US",
        "https://apps.jw.org/api/public/meeting-search?countryCode=US",
        "https://apps.jw.org/api/public/locations?countryCode=US",
    ]
    
    for url in endpoints:
        data = fetch_json(url)
        if data:
            congregations = data.get("data", []) or data.get("congregations", []) or data.get("results", [])
            for c in congregations:
                name = c.get("name", "") or c.get("congregationName", "")
                if name:
                    results.append({
                        "name": name.strip(),
                        "address": c.get("address", {}).get("street", "") if isinstance(c.get("address"), dict) else "",
                        "city": c.get("address", {}).get("city", "") if isinstance(c.get("address"), dict) else "",
                        "state": c.get("address", {}).get("state", "") if isinstance(c.get("address"), dict) else "",
                        "denomination": "Jehovah's Witnesses"
                    })
            if results:
                break
    
    print(json.dumps({"done": True, "total": len(results), "note": "JW data may be limited - no public congregation directory API exists"}))
    for r in results:
        print(json.dumps(r))

if __name__ == "__main__":
    main()

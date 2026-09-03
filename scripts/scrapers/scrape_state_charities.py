"""State Charity Registry Scraper — PA + OH
Uses search term dictionary to find religious orgs in state charity databases.
Extracts: org name, address, phone, email, EIN, filing status.
Matches results back to churches table.
"""
import urllib.request, urllib.parse, json, sqlite3, time, re
from datetime import datetime

DB = 'churches.db'
now = datetime.utcnow().isoformat()

# ── Search Term Dictionary ──
# Tier 1: High-yield generic terms
SEARCH_TERMS = [
    "church", "ministry", "temple", "synagogue", "mosque",
    "fellowship", "worship", "parish", "diocese", "cathedral",
    "chapel", "catholic", "baptist", "methodist", "presbyterian",
    "lutheran", "episcopal", "pentecostal", "evangelical",
    "assembly of god", "church of god", "church of christ",
    "seventh day adventist", "latter day saints", "orthodox",
    "buddhist", "hindu", "sikh", "jain", "muslim", "islamic",
    "jewish", "messianic", "covenant", "crusade", "mission",
    "gospel", "tabernacle", "revival", "outreach",
    "christian center", "worship center", "community church",
    "bible church", "faith church", "grace church", "hope church",
    "new life", "calvary", "vineyard", "cornerstone",
]

# ── PA Charity API Client ──
class PACharitySearch:
    BASE = "https://www.charities.pa.gov/api"
    
    def search(self, term, page=1, page_size=50):
        """Search PA charities by name. Returns list of org dicts."""
        # Try multiple endpoint/parameter formats
        formats = [
            # POST JSON
            (f"{self.BASE}/charities/search", "POST", 
             json.dumps({"charityName": term, "page": page, "pageSize": page_size}).encode(),
             {"Content-Type": "application/json"}),
            # GET query params
            (f"{self.BASE}/charities/search?{urllib.parse.urlencode({'name': term, 'page': page, 'pageSize': page_size})}",
             "GET", None, {}),
            # Alternate POST
            (f"{self.BASE}/CharitySearch", "POST",
             json.dumps({"searchTerm": term, "pageNumber": page, "pageSize": page_size}).encode(),
             {"Content-Type": "application/json"}),
        ]
        
        for url, method, data, headers in formats:
            try:
                req = urllib.request.Request(url, data=data, headers=headers or {})
                req.add_header('Accept', 'application/json')
                if method == "GET" and data:
                    req.method = "GET"
                
                with urllib.request.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read())
                    if result:
                        return result
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    body = e.read().decode(errors='replace')
                    print(f"  {method} {url}: HTTP {e.code} - {body[:100]}")
            except Exception as e:
                pass  # try next format
        
        return None

# ── Main ──
print("=== State Charity Registry Scraper ===\n")
pa = PACharitySearch()

# Test with first term
test_term = "church"
print(f"Testing PA API with '{test_term}'...")
result = pa.search(test_term)

if result:
    print(f"  Response type: {type(result).__name__}")
    if isinstance(result, dict):
        print(f"  Keys: {list(result.keys())}")
        # Check for results array
        for key in ['results', 'data', 'items', 'charities', 'list', 'records']:
            if key in result:
                items = result[key]
                print(f"  Found {len(items)} results in '{key}'")
                if items:
                    print(f"  Sample: {json.dumps(items[0], indent=2)[:500]}")
                break
    elif isinstance(result, list):
        print(f"  Array of {len(result)} items")
        if result:
            print(f"  Sample: {json.dumps(result[0], indent=2)[:500]}")
else:
    print("  All formats failed. Need to reverse-engineer via browser DevTools.")
    print("  Try: Open https://www.charities.pa.gov/#/page/searchCharities in browser")
    print("  Search for 'church', check Network tab for XHR requests.")

print("\nNext steps once API is working:")
print("  1. Loop through SEARCH_TERMS")
print("  2. Deduplicate results by EIN")
print("  3. Match to churches table by name+address")
print("  4. Upsert contact info (phone, email, address)")
print("  5. Repeat for Ohio, other states")

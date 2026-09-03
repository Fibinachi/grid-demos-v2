"""Test Google Knowledge Graph API for church enrichment"""
import urllib.request, json, os, time

API_KEY = os.environ.get("GOOGLE_KG_API_KEY", "")
if not API_KEY:
    raise ValueError("GOOGLE_KG_API_KEY environment variable is required")

def kg_search(query, limit=3):
    """Search Knowledge Graph for a church."""
    url = f"https://kgsearch.googleapis.com/v1/entities:search?query={urllib.request.quote(query)}&key={API_KEY}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}

# Test with a few churches
tests = [
    "Saddleback Church Lake Forest California",
    "Willow Creek Church South Barrington",
    "Hillsong Church",
    "First Baptist Church Dallas Texas",
]

for query in tests:
    print(f"\n=== {query} ===")
    result = kg_search(query)
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        continue
    
    items = result.get("itemListElement", [])
    print(f"  Results: {len(items)}")
    for item in items[:2]:
        entity = item.get("result", {})
        name = entity.get("name", "?")
        desc = entity.get("description", "")
        score = item.get("resultScore", 0)
        types = entity.get("@type", [])
        detail = entity.get("detailedDescription", {})
        detail_text = detail.get("articleBody", "")[:200] if detail else ""
        
        print(f"  [{score:.0f}] {name}")
        print(f"       Type: {', '.join(types[:3])}")
        print(f"       Desc: {desc}")
        if detail_text:
            print(f"       Detail: {detail_text}")
        
        # Get website and social links from the entity
        url = entity.get("url", "")
        print(f"       URL: {url}")
        
        # Check for sameAs links (social media, wikipedia, etc)
        same_as = entity.get("sameAs", [])
        if same_as:
            print(f"       Links: {', '.join(same_as[:3])}")
    
    time.sleep(0.5)  # Rate limit

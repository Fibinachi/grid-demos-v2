"""Research available Christian business directories and religious org sources."""
import urllib.request, json, re, sys

print("=== Christian Business Directories ===")
sources = [
    ("Christian Business Directory", "https://christianbusinessdirectory.com"),
    ("Christian Chamber", "https://christianchamber.com"),
    ("Godinterest", "https://godinterest.com/business"),
    ("Christian Business Network", "https://christianbusinessnetwork.com"),
    ("C12 Group", "https://www.c12group.com"),
]

for name, url in sources:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")
            print(f"  [{name}] {url}")
            # Check size and if searchable
            size = len(html)
            has_list = "directory" in html.lower() or "member" in html.lower() or "business" in html.lower()
            print(f"    Size: {size:,} bytes | Has listings: {has_list}")
    except Exception as e:
        print(f"  [{name}] ERROR: {str(e)[:60]}")

print()

# Also check: could we find X and B NTEE codes in our IRS data?
print("=== What we already have (IRS data) ===")
print("Total records in private_foundations_clean.csv: 142,791")
print("  Religion (X): 3,656")
print("  Education (B): 11,845")
print("  Private Foundations (T): 61,452")
print()
print("Total records in enriched_contacts.csv: 29,743 (theology-only)")
print("  25,838 with DNS-guessed emails")
print()
print("Potential expansion: process X and B codes too")
print(f"  That would add {3656+11845:,} more organizations")

# Check DuckDuckGo for Christian business lists
print("\n=== Searching for Christian business contact lists ===")
try:
    from duckduckgo_search import DDGS
    queries = [
        "Christian business directory CSV",
        "Christian-owned businesses list USA",
        "faith-based business directory download",
        "Christian Chamber of Commerce directory",
    ]
    for q in queries:
        with DDGS() as ddgs:
            results = list(ddgs.text(q, max_results=3))
            print(f"\n  Query: {q}")
            for r in results:
                snippet = r.get("body","")[:150]
                title = r.get("title","")
                print(f"    [{title[:50]}] {snippet}") 
except ImportError:
    print("  duckduckgo_search not available")
except Exception as e:
    print(f"  Error: {str(e)[:80]}")

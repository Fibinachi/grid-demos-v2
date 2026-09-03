"""Quick test for ES scraper - test query_state"""
from scrape_shepherds import query_state

recs = query_state(14, "AL", size=100)
print(f"Got {len(recs)} records")
for r in recs[:3]:
    print(f"  {r['name'][:40]} | {r['phone']} | {r['state']}")
# Check total across first 3 pages
recs2 = query_state(14, "AL", size=200)
print(f"With size=200: {len(recs2)} records")

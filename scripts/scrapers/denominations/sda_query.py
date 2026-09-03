"""Query Shepherd's Stream ES for SDA churches"""
from scrape_shepherds import fetch_es

params = {"index": "shepherdsstream", "q": "taxonomy.jreviews_jr_denomination:*adventist*", "size": 5}
data = fetch_es(params)
if data:
    total = data.get("hits",{}).get("total",{}).get("value",0)
    print(f"SDA churches found: {total}")
    for h in data.get("hits",{}).get("hits",[]):
        s = h["_source"]
        t = s.get("taxonomy",[{}])[0]
        print(f"  {s['title'][:50]} | {t.get('jreviews_jr_state','')} | {t.get('jreviews_jr_denomination','')[:40]}")
else:
    print("Query failed")

# Also try a broader search for Seventh-day
params2 = {"index": "shepherdsstream", "q": "title:*seventh-day*", "size": 5}
data2 = fetch_es(params2)
if data2:
    total2 = data2.get("hits",{}).get("total",{}).get("value",0)
    print(f"Seventh-day churches found: {total2}")
# Try SDA abbreviation
params3 = {"index": "shepherdsstream", "q": "title:*SDA*", "size": 3}
data3 = fetch_es(params3)
if data3:
    total3 = data3.get("hits",{}).get("total",{}).get("value",0)
    print(f"SDA abbreviation churches: {total3}")

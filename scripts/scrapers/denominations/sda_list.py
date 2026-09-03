"""Download all SDA churches from Shepherd's Stream ES"""
from scrape_shepherds import fetch_es, STATE_IDS
import json, re, os

def is_sda(name, denom):
    name_upper = (name or "").upper()
    denom_upper = (denom or "").upper()
    # Check various SDA indicators
    if "SEVENTH-DAY ADVENTIST" in name_upper or "SEVENTH DAY ADVENTIST" in name_upper:
        return True
    if re.search(r'\bSDA\b', name_upper) or name_upper.endswith(' SDA') or name_upper.startswith('SDA '):
        return True
    if "ADVENTIST" in denom_upper:
        return True
    if "ADVENTIST" in name_upper and "SEVENTH" in name_upper:
        return True
    return False

# Search by denomination keyword for SDA
all_results = []
for keyword in ["Adventist"]:
    params = {"index": "shepherdsstream", "q": f"title:*{keyword}*", "size": 1000}
    data = fetch_es(params)
    if data:
        total = data.get("hits",{}).get("total",{}).get("value",0)
        print(f"'{keyword}' in title: {total}")
        for h in data.get("hits",{}).get("hits",[]):
            s = h["_source"]
            t = s.get("taxonomy",[{}])[0]
            name = s.get("title","")
            denom = t.get("jreviews_jr_denomination","")
            if is_sda(name, denom):
                all_results.append({
                    "name": name,
                    "state": t.get("jreviews_jr_state",""),
                    "city": t.get("jreviews_jr_city",""),
                    "phone": t.get("jreviews_jr_mainphone",""),
                    "website": t.get("jreviews_jr_website",""),
                    "denomination": denom,
                    "address": t.get("jreviews_jr_address",""),
                    "zip": t.get("jreviews_jr_zipcode",""),
                })

# Also search denomination field
params2 = {"index": "shepherdsstream", "q": "taxonomy.jreviews_jr_denomination:*adventist*", "size": 1000}
data2 = fetch_es(params2)
if data2:
    total2 = data2.get("hits",{}).get("total",{}).get("value",0)
    print(f"Denom field 'adventist': {total2}")
    for h in data2.get("hits",{}).get("hits",[]):
        s = h["_source"]
        t = s.get("taxonomy",[{}])[0]
        name = s.get("title","")
        all_results.append({
            "name": name,
            "state": t.get("jreviews_jr_state",""),
            "city": t.get("jreviews_jr_city",""),
            "phone": t.get("jreviews_jr_mainphone",""),
            "website": t.get("jreviews_jr_website",""),
            "denomination": t.get("jreviews_jr_denomination",""),
            "address": t.get("jreviews_jr_address",""),
            "zip": t.get("jreviews_jr_zipcode",""),
        })

# Deduplicate by name+state
seen = set()
unique = []
for r in all_results:
    key = (r["name"].lower().strip(), (r.get("state","") or "").upper())
    if key not in seen:
        seen.add(key)
        unique.append(r)

print(f"\nTotal unique SDA: {len(unique)}")
print()
# Group by state
from collections import Counter
states = Counter(r.get("state","") for r in unique)
print("By state:")
for s, c in states.most_common():
    print(f"  {s}: {c}")

print(f"\nFirst 20:")
for r in unique[:20]:
    url = r.get("website","")[:35] if r.get("website") else ""
    print(f"  {r['name'][:50]:50s} | {r.get('state',''):2s} | {r.get('phone',''):15s} | {url}")

# Save
out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sda_churches.json")
json.dump(unique, open(out_path,"w"), indent=2)
print(f"\nSaved to {out_path}")

"""
Fetch all Jain temple data from jain.wiki SPARQL endpoint.
Endpoint: https://data.jain.wiki/query/sparql
"""
import requests, json, time
from pathlib import Path

OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)

H = {"User-Agent": "GRID/1.0", "Accept": "application/sparql-results+json"}
SPARQL = "https://data.jain.wiki/query/sparql"

# Step 1: Count total
count_query = """
PREFIX yp: <https://data.jain.wiki/prop/direct/>
SELECT (COUNT(?item) AS ?count) WHERE {
  ?item yp:P1 ?type.
  ?item yp:P9 ?lat.
  ?item yp:P10 ?lon.
}
"""
r = requests.get(SPARQL, params={"query": count_query.strip(), "format": "json"}, headers=H, timeout=30)
print(f"Count query: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    count = data.get("results",{}).get("bindings",[{}])[0].get("count",{}).get("value","?")
    print(f"Total temples with coordinates: {count}")

# Step 2: Fetch all temples with coordinates
print("\nFetching all temples...")
query = """
PREFIX yp: <https://data.jain.wiki/prop/direct/>
PREFIX yq: <https://data.jain.wiki/entity/>
SELECT ?item ?itemLabel ?lat ?lon ?type ?typeLabel ?sect ?sectLabel ?city ?cityLabel ?state ?stateLabel ?country ?countryLabel WHERE {
  ?item yp:P1 ?type.
  ?item yp:P9 ?lat.
  ?item yp:P10 ?lon.
  OPTIONAL { ?item yp:P3 ?sect. }
  OPTIONAL { ?item yp:P4 ?city. }
  OPTIONAL { ?item yp:P5 ?state. }
  OPTIONAL { ?item yp:P7 ?country. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10000
"""
r2 = requests.get(SPARQL, params={"query": query.strip(), "format": "json"}, headers=H, timeout=120)
print(f"Fetch: {r2.status_code}, Size: {len(r2.text)} bytes")

if r2.status_code == 200:
    result = r2.json()
    bindings = result.get("results", {}).get("bindings", [])
    print(f"Temples: {len(bindings)}")
    
    records = []
    for b in bindings:
        rec = {
            "name": b.get("itemLabel", {}).get("value", ""),
            "item": b.get("item", {}).get("value", ""),
            "lat": float(b.get("lat", {}).get("value", 0)),
            "lon": float(b.get("lon", {}).get("value", 0)),
            "type": b.get("typeLabel", {}).get("value", ""),
            "sect": b.get("sectLabel", {}).get("value", ""),
            "city": b.get("cityLabel", {}).get("value", ""),
            "state": b.get("stateLabel", {}).get("value", ""),
            "country": b.get("countryLabel", {}).get("value", ""),
        }
        records.append(rec)
    
    # Show sample
    print(f"\nFirst 10 records:")
    for r in records[:10]:
        print(f"  {r['name'][:50]:50s} | {r['type']:25s} | {r['city']:20s} | {r['state']:20s}")
    
    # Count by type
    from collections import Counter
    types = Counter(r['type'] for r in records)
    print(f"\nBy type:")
    for t, c in types.most_common(10):
        print(f"  {t}: {c}")
    
    # Count by state
    states = Counter(r['state'] for r in records if r['state'])
    print(f"\nBy state (top 10):")
    for s, c in states.most_common(10):
        print(f"  {s}: {c}")
    
    # Save
    json.dump(records, open(OUT / "jain_wiki_temples.json", "w", encoding="utf-8"), indent=2)
    print(f"\nSaved to {OUT}/jain_wiki_temples.json")
    
    # Import into churches.db
    print("\n=== Importing into churches.db ===")
    import sqlite3
    db = sqlite3.connect("churches.db")
    imported = 0
    for rec in records:
        name = rec["name"]
        if not name:
            continue
        item_id = rec["item"].split("/")[-1] if rec["item"] else ""
        # Check if already exists
        exists = db.execute("SELECT id FROM churches WHERE source='jainwiki' AND source_id=?", (item_id,)).fetchone()
        if not exists:
            db.execute("""INSERT INTO churches 
                (name, faith, tradition, latitude, longitude, city, state, country, source, source_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name[:500], "Jain", rec["sect"][:100] if rec["sect"] else None, 
                 rec["lat"], rec["lon"], rec["city"][:100], rec["state"][:100], 
                 rec.get("country", "IN")[:100], "jainwiki", item_id, "active"))
            imported += 1
        else:
            # Update existing with more detail if available
            eid = exists[0]
            if rec["sect"]:
                db.execute("UPDATE churches SET tradition = COALESCE(NULLIF(tradition,''), ?) WHERE id=?", (rec["sect"][:100], eid))
    db.commit()
    db.close()
    print(f"Imported {imported} new, updated existing")
else:
    print(f"Error: {r2.text[:500]}")

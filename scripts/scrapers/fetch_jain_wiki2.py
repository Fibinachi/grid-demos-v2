"""
Fetch all Jain temples from jain.wiki SPARQL — with CORRECT property IDs.
P1 = type, P2 = location (globe-coordinate), P4 = city, P7 = country
"""
import requests, json, time
from pathlib import Path
from collections import Counter

OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "GRID/1.0", "Accept": "application/sparql-results+json"}
SPARQL = "https://data.jain.wiki/query/sparql"

# Step 1: Count items with P2 (location/coordinate)
print("=== Step 1: Count ===")
q1 = """
PREFIX yp: <https://data.jain.wiki/prop/direct/>
SELECT (COUNT(?item) AS ?count) WHERE { ?item yp:P2 [] . }
"""
r = requests.get(SPARQL, params={"query": q1.strip(), "format": "json"}, headers=H, timeout=30)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    d = r.json()
    count = d.get("results",{}).get("bindings",[{}])[0].get("count",{}).get("value","?")
    print(f"Items with coordinates: {count}")

# Step 2: Fetch items with P1 (type) = Temple
print("\n=== Step 2: Fetch temples with coordinates ===")
q2 = """
PREFIX yp: <https://data.jain.wiki/prop/direct/>
SELECT ?item ?itemLabel ?type ?typeLabel ?city ?cityLabel ?state ?stateLabel ?country ?countryLabel ?sect ?sectLabel WHERE {
  ?item yp:P1 ?type.
  ?item yp:P2 [] .
  OPTIONAL { ?item yp:P4 ?city. }
  OPTIONAL { ?item yp:P5 ?state. }
  OPTIONAL { ?item yp:P7 ?country. }
  OPTIONAL { ?item yp:P3 ?sect. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10000
"""
r2 = requests.get(SPARQL, params={"query": q2.strip(), "format": "json"}, headers=H, timeout=120)
print(f"Status: {r2.status_code}, Size: {len(r2.text)} bytes")

if r2.status_code == 200:
    result = r2.json()
    bindings = result.get("results", {}).get("bindings", [])
    print(f"Temples: {len(bindings)}")
    
    # Show types
    types = Counter(b.get("typeLabel",{}).get("value","?") for b in bindings)
    print(f"\nTypes:")
    for t, c in types.most_common():
        print(f"  {t}: {c}")
    
    # Show a sample
    print(f"\nSample records:")
    for b in bindings[:5]:
        name = b.get("itemLabel",{}).get("value","")
        typ = b.get("typeLabel",{}).get("value","")
        city = b.get("cityLabel",{}).get("value","")
        state = b.get("stateLabel",{}).get("value","")
        print(f"  {name[:50]:50s} | {typ:25s} | {city:20s} | {state:20s}")
    
    # The coordinates are in P2 as globe-coordinate — we need to get them via a different query
    # Let's try fetching the actual coordinate values
    print("\n=== Step 3: Fetch lat/lon via separate query ===")
    q3 = """
    PREFIX yp: <https://data.jain.wiki/prop/direct/>
    SELECT ?item ?itemLabel ?loc WHERE {
      ?item yp:P1 ?type.
      ?item yp:P2 ?loc.
    }
    LIMIT 100
    """
    r3 = requests.get(SPARQL, params={"query": q3.strip(), "format": "json"}, headers=H, timeout=60)
    print(f"Status: {r3.status_code}, Size: {len(r3.text)} bytes")
    if r3.status_code == 200:
        d3 = r3.json()
        b3 = d3.get("results",{}).get("bindings",[])
        print(f"Results: {len(b3)}")
        for b in b3[:3]:
            name = b.get("itemLabel",{}).get("value","")
            loc = b.get("loc",{}).get("value","")
            print(f"  {name[:50]:50s} -> {loc}")
    else:
        print(f"Error: {r3.text[:300]}")
else:
    print(f"Error: {r2.text[:500]}")

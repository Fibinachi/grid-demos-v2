"""Test various jain.wiki API/SPARQL endpoints."""
import requests

H = {"User-Agent": "GRID/1.0"}
endpoints = [
    "https://data.jain.wiki/sparql",
    "https://data.jain.wiki/query/sparql", 
    "https://data.jain.wiki/api.php",
    "https://data.jain.wiki/w/api.php",
    "https://data.jain.wiki/wiki/Special:EntityData/Q12.json",
]
for ep in endpoints:
    try:
        r = requests.get(ep, headers=H, timeout=10)
        print(f"{ep}: {r.status_code} ({len(r.text)} bytes)")
        if r.status_code == 200 and "Q12" in ep:
            d = r.json()
            entities = d.get("entities", {})
            for k, v in entities.items():
                label = v.get("labels", {}).get("en", {}).get("value", "?")
                print(f"  Entity: {label}")
    except Exception as e:
        print(f"{ep}: ERROR {e}")

# Test SPARQL with a proper query
print("\n=== SPARQL Test ===")
sparql = "SELECT ?item ?itemLabel WHERE { ?item ?p ?o } LIMIT 5"
params = {"query": sparql, "format": "json"}
r = requests.get("https://data.jain.wiki/sparql", params=params, headers=H, timeout=15)
print(f"SPARQL: {r.status_code} ({len(r.text)} bytes)")
if r.status_code == 200:
    print(r.text[:500])

# Try the MediaWiki API for places
print("\n=== MediaWiki API ===")
params2 = {
    "action": "query",
    "list": "allpages",
    "apnamespace": "0",
    "aplimit": "10",
    "format": "json"
}
r2 = requests.get("https://data.jain.wiki/w/api.php", params=params2, headers=H, timeout=15)
print(f"MediaWiki: {r2.status_code} ({len(r2.text)} bytes)")
if r2.status_code == 200:
    print(r2.text[:500])

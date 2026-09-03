"""
Import all 8,096 Jain sites from jain.wiki into churches.db.
SPARQL endpoint: https://data.jain.wiki/query/sparql
"""
import requests, json, re, time
from pathlib import Path
from collections import Counter

OUT = Path("data/jainmandir")
OUT.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "GRID/1.0", "Accept": "application/sparql-results+json"}
SPARQL = "https://data.jain.wiki/query/sparql"

# Fetch with coordinates
print("=== Fetching all Jain wiki data ===")
q = """
PREFIX yp: <https://data.jain.wiki/prop/direct/>
PREFIX yq: <https://data.jain.wiki/entity/>
SELECT ?item ?itemLabel ?type ?typeLabel ?loc ?city ?cityLabel ?state ?stateLabel ?country ?countryLabel ?sect ?sectLabel WHERE {
  ?item yp:P1 ?type.
  ?item yp:P2 ?loc.
  OPTIONAL { ?item yp:P4 ?city. }
  OPTIONAL { ?item yp:P5 ?state. }
  OPTIONAL { ?item yp:P7 ?country. }
  OPTIONAL { ?item yp:P3 ?sect. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
LIMIT 10000
"""
r = requests.get(SPARQL, params={"query": q.strip(), "format": "json"}, headers=H, timeout=180)
print(f"Status: {r.status_code}, Size: {len(r.text)} bytes")

if r.status_code != 200:
    print(f"ERROR: {r.text[:500]}")
    exit(1)

bindings = r.json().get("results", {}).get("bindings", [])
print(f"\nTotal records: {len(bindings)}")

# Parse into records
records = []
for b in bindings:
    loc_str = b.get("loc", {}).get("value", "")
    lat, lon = None, None
    # Parse WKT Point(lon lat)
    m = re.match(r"Point\(([\d.-]+)\s+([\d.-]+)\)", loc_str, re.IGNORECASE)
    if m:
        lon, lat = float(m.group(1)), float(m.group(2))
    
    item_id = b.get("item", {}).get("value", "").split("/")[-1]
    
    rec = {
        "name": b.get("itemLabel", {}).get("value", ""),
        "item_id": item_id,
        "type": b.get("typeLabel", {}).get("value", ""),
        "latitude": lat,
        "longitude": lon,
        "sect": b.get("sectLabel", {}).get("value", ""),
        "city": b.get("cityLabel", {}).get("value", ""),
        "state": b.get("stateLabel", {}).get("value", ""),
        "country": b.get("countryLabel", {}).get("value", ""),
    }
    records.append(rec)

# Stats
types = Counter(r["type"] for r in records)
traditions = Counter(r["sect"] for r in records if r["sect"])
print(f"\nTypes: {dict(types.most_common())}")
if traditions:
    print(f"Traditions: {dict(traditions.most_common(10))}")

# Show sample
print(f"\nSample records:")
for r in records[:5]:
    print(f"  {r['name'][:55]:55s} | {r['latitude']:8.4f} {r['longitude']:8.4f} | {r['type']:20s} | {r['city']:20s} | {r['state']:20s}")

# Save raw
json.dump(records, open(OUT / "jain_wiki_temples.json", "w", encoding="utf-8"), indent=2)
print(f"\nSaved raw JSON to {OUT}/jain_wiki_temples.json")

# Import into churches.db
print(f"\n{'='*60}")
print("IMPORTING INTO churches.db")
print(f"{'='*60}")
import sqlite3
db = sqlite3.connect("churches.db")

imported = 0
updated = 0
skipped = 0

for i, rec in enumerate(records):
    name = rec["name"]
    if not name or not rec["latitude"] or not rec["longitude"]:
        skipped += 1
        continue
    
    item_id = rec["item_id"]
    lat = rec["latitude"]
    lon = rec["longitude"]
    
    # Check if already exists by lat/lon proximity (within ~100m)
    existing = db.execute(
        "SELECT id FROM churches WHERE faith='Jain' AND ABS(latitude-?)<0.001 AND ABS(longitude-?)<0.001",
        (lat, lon)
    ).fetchone()
    
    if existing:
        skipped += 1
    else:
        # Insert new
        db.execute("""INSERT INTO churches 
            (name, faith, tradition, landmark_type, latitude, longitude, 
             city, state, country, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name[:500], "Jain", rec["sect"][:100] if rec["sect"] else None,
             rec["type"].lower().replace(" ", "_")[:50],
             lat, lon,
             rec["city"][:100] if rec["city"] else None,
             rec["state"][:100] if rec["state"] else None,
             rec["country"][:100] if rec["country"] else "IN",
             "jainwiki"))
        imported += 1
    
    if (i + 1) % 1000 == 0:
        db.commit()
        print(f"  Progress: {i+1}/{len(records)} (imported {imported}, updated {updated}, skipped {skipped})")

db.commit()
db.close()

print(f"\n{'='*60}")
print(f"IMPORT COMPLETE")
print(f"{'='*60}")
print(f"  Imported:  {imported}")
print(f"  Updated:   {updated}")
print(f"  Skipped:   {skipped}")
print(f"  Total:     {len(records)}")

# Verify
db2 = sqlite3.connect("churches.db")
jain_total = db2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain'").fetchone()[0]
jain_new = db2.execute("SELECT COUNT(*) FROM churches WHERE faith='Jain' AND source='jainwiki'").fetchone()[0]
print(f"\n  Jain total in DB: {jain_total}")
print(f"  From jain.wiki:   {jain_new}")
db2.close()

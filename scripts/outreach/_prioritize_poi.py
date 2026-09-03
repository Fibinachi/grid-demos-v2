"""Find and prioritize POI/location data buyers in queue."""
import json
from pathlib import Path

QF = Path("outputs/outreach/unified_queue.jsonl")
entries = [json.loads(l) for l in QF.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

# Real POI/location data companies only (not publishers, churches, etc.)
POI_EMAILS = {
    "privacyteam@foursquare.com", "press@safegraph.com",
    "privacy@placeexchange.com", "placeiq.privacy@precisely.com",
    "consumerprivacy@buxtonco.com", "globalprivacyinbox@costar.com",
    "privacy@propertyradar.com",
    "privacy@blis.com", "legal@cuebiq.com",
    "privacy@matchbookdata.com", "privacy@outlogic.io",
    "privacy@quadrant.io", "info@revealmobile.com",
    "tax@veraset.com", "jfranks@lightboxre.com",
}

poi_entries = [e for e in entries if e.get("to", "").lower() in POI_EMAILS]
rest = [e for e in entries if e.get("to", "").lower() not in POI_EMAILS]

print(f"POI/location companies: {len(poi_entries)}")
for p in poi_entries:
    print(f"  {p.get('category','?'):20s} | {p.get('org','?')[:50]:50s} -> {p['to']}")

# Move POI entries to very top
new_entries = poi_entries + rest

with open(QF, "w", encoding="utf-8") as f:
    for item in new_entries:
        f.write(json.dumps(item) + "\n")

print(f"\nQueue reordered. First 10:")
for e in new_entries[:10]:
    is_poi = "POI" if e.get("to", "").lower() in POI_EMAILS else "   "
    print(f"  {is_poi} | {e.get('org','?')[:48]:48s} -> {e['to']}")

print(f"\nTotal: {len(new_entries)} entries.")

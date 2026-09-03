"""Move academics right behind POI/enterprise buyers."""
import json; from pathlib import Path

QF = Path("outputs/outreach/unified_queue.jsonl")
entries = [json.loads(l) for l in QF.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

# POI emails (currently at top)
POI_SOURCES = {"cppa_safegraph"}
POI_KW = ["foursquare", "safegraph", "place exchange", "placeiq", "buxton",
          "costar", "propertyradar", "blis global", "cuebiq", "matchbook",
          "outlogic", "quadrant", "reveal mobile", "veraset", "lightbox"]

poi_emails = set()
for e in entries:
    org_lower = (e.get("org", "") + " " + e.get("to", "")).lower()
    if e.get("source") in POI_SOURCES or any(kw in org_lower for kw in POI_KW):
        poi_emails.add(e["to"].lower())

poi = [e for e in entries if e["to"].lower() in poi_emails]
academic = [e for e in entries if e.get("source") == "academic"]
rest = [e for e in entries if e["to"].lower() not in poi_emails and e.get("source") != "academic"]

new_entries = poi + academic + rest
with open(QF, "w", encoding="utf-8") as f:
    for item in new_entries:
        f.write(json.dumps(item) + "\n")

print(f"POI: {len(poi)} | Academic: {len(academic)} | Rest: {len(rest)} | Total: {len(new_entries)}")
print("\nFirst 25:")
for i, e in enumerate(new_entries[:25]):
    src = e.get("source", "?")
    org = e.get("org", "?")[:40]
    tag = "POI" if e["to"].lower() in poi_emails else ("ACAD" if e.get("source") == "academic" else "   ")
    print(f"  {i+1:2d} {tag} | {org:40s} -> {e['to']}")

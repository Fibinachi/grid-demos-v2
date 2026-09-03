import json, os, time, urllib.request

RAW_PATH = "data/arcgis/arcgis_catalog_raw.json"
with open(RAW_PATH, "r", encoding="utf-8") as f:
    raw = json.load(f)

datasets = raw.get("datasets", [])
print(f"Loaded {len(datasets):,} datasets")

fs_datasets = [ds for ds in datasets if "/FeatureServer" in (ds.get("url","") or "")]
print(f"FeatureService datasets: {len(fs_datasets):,}")

# Quick summary by title keywords
key_cats = {"worship":0, "church":0, "mosque":0, "synagog":0, "temple":0, "religi":0, "faith":0, "meetinghouse":0}
other_cats = {}
for ds in fs_datasets:
    t = (ds.get("title","") + " " + (ds.get("description","") or "") + " " + (ds.get("snippet","") or "")).lower()
    matched = False
    for kw in key_cats:
        if kw in t:
            key_cats[kw] += 1
            matched = True
    if not matched:
        # Categorize by owner
        owner = ds.get("owner","") or "unknown"
        other_cats[owner] = other_cats.get(owner, 0) + 1

print("\n--- Keyword matches in titles/descriptions ---")
for k,v in sorted(key_cats.items(), key=lambda x:-x[1]):
    print(f"  '{k}': {v:,} datasets")
print(f"\n   Not matching any keyword: {sum(other_cats.values()):,} (distinct owners: {len(other_cats)})")
print(f"\nTop 20 owners by count:")
for o,c in sorted(other_cats.items(), key=lambda x:-x[1])[:20]:
    print(f"  {o}: {c}")

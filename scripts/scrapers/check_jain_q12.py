"""Inspect Q12 entity to find property IDs."""
import requests, json

H = {"User-Agent": "GRID/1.0"}
r = requests.get("https://data.jain.wiki/wiki/Special:EntityData/Q12.json", headers=H, timeout=15)
d = r.json()
entities = d.get("entities", {})
for qid, entity in entities.items():
    print(f"Entity: {qid}")
    label = entity.get("labels", {}).get("en", {}).get("value", "?")
    print(f"  Label: {label}")
    claims = entity.get("claims", {})
    for prop, claim_list in claims.items():
        mainsnak = claim_list[0].get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value", {})
        datatype = mainsnak.get("datatype", "?")
        if isinstance(value, dict):
            val_str = value.get("id", value.get("text", str(value)[:80]))
        else:
            val_str = str(value)[:80]
        print(f"  {prop}: {val_str} ({datatype})")

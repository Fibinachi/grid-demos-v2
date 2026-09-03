"""Investigate NHL unmatched records for Saint/St. name standardization issues"""
import json

import io
d = json.load(io.open("E:/grid/data/nhl_unmatched.json", encoding="utf-8"))
print(f"Total unmatched: {len(d)}")

# Saint/St./San/Santa patterns
saints = [e for e in d if "st." in e["nhl_name"].lower() or "saint" in e["nhl_name"].lower() or "san " in e["nhl_name"].lower() or "santa " in e["nhl_name"].lower()]
print(f"\nWith Saint/St./San/Santa in name: {len(saints)}")
for e in saints[:25]:
    print(f"  {e['nhl_name']:45s}  @ {e['location']}")

# Also check "church" variants - maybe "church" vs "chapel" etc
print(f"\n--- All unmatched ---")
for i, e in enumerate(d):
    print(f"  {i+1:3d}. {e['nhl_name']:50s}  @ {e['location']}")

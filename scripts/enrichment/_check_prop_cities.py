"""Check what cities the property records use."""
import json

with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

from collections import Counter
cities = Counter()
for p in props:
    c = (p.get('CITY') or '?').strip().upper()
    cities[c] += 1

print("Cities in property records:")
for c, cnt in cities.most_common():
    print(f"  {c}: {cnt}")

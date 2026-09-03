"""Verify Cape Town is Web Mercator."""
from pyproj import Transformer
import csv

with open('Places_of_Worship_Capetown.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

t = Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True)
print("Testing EPSG:3857 (Web Mercator) on first 5 rows:")
for r in rows[:5]:
    x, y = float(r['X']), float(r['Y'])
    lon, lat = t.transform(x, y)
    print(f"  ({x:.1f}, {y:.1f}) -> ({lon:.4f}, {lat:.4f})  {r['NAME'][:50]}")

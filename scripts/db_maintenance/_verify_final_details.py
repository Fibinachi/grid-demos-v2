"""Verify TU_Places CRS and check Places5 vs Places12 content."""
from pyproj import Transformer
import csv

# TU_Places - x=-8.36M, y=4.86M → likely EPSG:3857 Web Mercator → Philadelphia
with open('TU_Places_of_Worship.csv', encoding='utf-8-sig') as f:
    tu = list(csv.DictReader(f))

t = Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True)
for r in tu[:3]:
    x, y = float(r['X']), float(r['Y'])
    lon, lat = t.transform(x, y)
    print(f"  TU: ({lon:.4f}, {lat:.4f})  {r['Name'][:50]} — {'✓ PHILADELPHIA' if abs(lon+75.2)<0.5 else 'WRONG'}")

# Check Places5 vs Places12 - same data?
print("\n=== Places5 vs Places12 content comparison ===")
with open('Places_of_Worship5.csv', encoding='utf-8-sig') as f:
    p5 = list(csv.DictReader(f))
with open('Places_of_Worship12.csv', encoding='utf-8-sig') as f:
    p12 = list(csv.DictReader(f))

print(f"Places5 cols: {list(p5[0].keys())}")
print(f"Places12 cols: {list(p12[0].keys())}")

names5 = sorted([r.get('PlaceOfWorshipName','') for r in p5])
names12 = sorted([r.get('PlaceOfWorshipName','') for r in p12])
print(f"Same names: {names5 == names12}")
print(f"5 sample: {names5[0][:50]}, {names5[-1][:50]}")
print(f"12 sample: {names12[0][:50]}, {names12[-1][:50]}")

# Check if same data, just different coords
t_2283 = Transformer.from_crs('EPSG:2283', 'EPSG:4326', always_xy=True)
t_2284 = Transformer.from_crs('EPSG:2284', 'EPSG:4326', always_xy=True)
for i in range(min(3, len(p5))):
    lon5, lat5 = t_2283.transform(float(p5[i]['X']), float(p5[i]['Y']))
    lon12, lat12 = t_2283.transform(float(p12[i]['X']), float(p12[i]['Y']))
    print(f"  [{i}] 5: ({lon5:.4f}, {lat5:.4f}) 12: ({lon12:.4f}, {lat12:.4f})  match: {abs(lon5-lon12)<0.001 and abs(lat5-lat12)<0.001}")

# Check Places2 names
print("\n=== Places2 names ===")
with open('Places_of_Worship2.csv', encoding='utf-8-sig') as f:
    p2 = list(csv.DictReader(f))
for r in p2:
    print(f"  NAME={r['NAME'][:40]} | TYPE={r.get('TYPE','?')[:30]} | LABEL={r.get('LABEL','')[:30]}")

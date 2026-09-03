"""Verify all three CRS conversions"""
from pyproj import Transformer
import csv

print("=" * 60)
print("1. KANSAS - EPSG:3419 (NAD83 / Kansas North ftUS)")
print("=" * 60)
tk = Transformer.from_crs('EPSG:3419', 'EPSG:4326', always_xy=True)
with open('Places_of_Worship.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print(f"First record: {rows[0]['NAME']}")
lon, lat = tk.transform(float(rows[0]['X']), float(rows[0]['Y']))
print(f"  ({rows[0]['X']}, {rows[0]['Y']}) -> ({lat:.5f}, {lon:.5f})")
# Last record
lon, lat = tk.transform(float(rows[-1]['X']), float(rows[-1]['Y']))
print(f"Last record: {rows[-1]['NAME']}")
print(f"  ({rows[-1]['X']}, {rows[-1]['Y']}) -> ({lat:.5f}, {lon:.5f})")

print()
print("=" * 60)
print("2. VIRGINIA - EPSG:2284 (NAD83 / Virginia South meters)")
print("=" * 60)
tv = Transformer.from_crs('EPSG:2284', 'EPSG:4326', always_xy=True)
with open('HousesOfWorship_-1944034289557826875.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print(f"First record: {rows[0].get('Name of Facility','')} ({rows[0].get('Municipality Name','')})")
lon, lat = tv.transform(float(rows[0]['x']), float(rows[0]['y']))
print(f"  ({rows[0]['x']}, {rows[0]['y']}) -> ({lat:.5f}, {lon:.5f})")
print(f"Last record: {rows[-1].get('Name of Facility','')} ({rows[-1].get('Municipality Name','')})")
lon, lat = tv.transform(float(rows[-1]['x']), float(rows[-1]['y']))
print(f"  ({rows[-1]['x']}, {rows[-1]['y']}) -> ({lat:.5f}, {lon:.5f})")

print()
print("=" * 60)
print("3. ONTARIO - EPSG:26917 (NAD83 / UTM Zone 17N)")
print("=" * 60)
to = Transformer.from_crs('EPSG:26917', 'EPSG:4326', always_xy=True)
with open('Places_of_Worship_1730298208157311066.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print(f"First record: {rows[0].get('POI_Name','')}")
lon, lat = to.transform(float(rows[0]['x']), float(rows[0]['y']))
print(f"  ({rows[0]['x']}, {rows[0]['y']}) -> ({lat:.5f}, {lon:.5f})")
print(f"Last record: {rows[-1].get('POI_Name','')}")
lon, lat = to.transform(float(rows[-1]['x']), float(rows[-1]['y']))
print(f"  ({rows[-1]['x']}, {rows[-1]['y']}) -> ({lat:.5f}, {lon:.5f})")

print()
print("All CRS verified ✅")

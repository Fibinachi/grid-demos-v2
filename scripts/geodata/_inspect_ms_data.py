"""Inspect the MS churches data more carefully - check communities, addresses, and coordinate ranges."""
import csv
from collections import Counter

with open('Churches_4106776180121190077.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
print(f"Columns: {list(rows[0].keys())}")
print()

# Communities
communities = Counter(r['COMMUNITY'] for r in rows)
print("=== Communities ===")
for c, n in communities.most_common():
    print(f"  {c}: {n}")
print()

# Coordinate ranges
xs = [float(r['x']) for r in rows]
ys = [float(r['y']) for r in rows]
print(f"X range: {min(xs):.2f} - {max(xs):.2f}")
print(f"Y range: {min(ys):.2f} - {max(ys):.2f}")
print()

# Sample locations
print("=== Sample locations ===")
for r in rows[:10]:
    print(f"  {r['LOCATION'][:60]:60s} | {r['FULL_ADDR'][:50]:50s} | {r['ZIP_CODE']} | {r.get('WEBSITE','')[:30]}")

# Check ZIP codes
zips = Counter(r['ZIP_CODE'] for r in rows)
print("\n=== ZIP codes ===")
for z, n in zips.most_common(10):
    print(f"  {z}: {n}")

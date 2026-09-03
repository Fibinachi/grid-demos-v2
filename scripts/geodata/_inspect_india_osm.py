"""Inspect the India OSM places_of_worship dataset to see what's in it."""
import csv
from collections import Counter

with open('OpenStreetMap_-_Place_of_Worship_(Point) India.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

print(f"Total rows: {len(rows)}")
print(f"Columns: {list(rows[0].keys())}")
print()

# fclass values (OSM feature type)
fclasses = Counter(r['fclass'] for r in rows)
print("=== OSM fclass (feature type) distribution ===")
for cls, cnt in fclasses.most_common(40):
    print(f"  {cls}: {cnt:,}")
print(f"  ... ({len(fclasses)} total classes)")
print()

# Check if any non-worship classes exist
non_worship = [c for c in fclasses if c not in ('place_of_worship', 'christian', 'muslim', 'hindu', 'buddhist', 'jewish', 'sikh', 'jain', 'shinto', 'taoist', 'bahai', 'pagan', 'church', 'mosque', 'temple', 'synagogue', 'gurdwara', 'monastery', 'cathedral', 'chapel', 'shrine', 'altar', 'wayside_shrine', 'wayside_cross')]
print(f"Classes that don't look religious: {non_worship}")
print()

# Show all unique classes sorted
print("=== ALL unique fclass values ===")
for cls in sorted(fclasses):
    print(f"  {cls}: {fclasses[cls]:,}")
print()

# Sample names
print("=== Sample names from top classes ===")
for cls, cnt in fclasses.most_common(3):
    print(f"\n--- {cls} ({cnt:,}) ---")
    shown = set()
    for r in rows:
        n = r['name'].strip()
        if r['fclass'] == cls and n and n not in shown:
            print(f"    {n[:70]}")
            shown.add(n)
            if len(shown) >= 5:
                break

# States represented
from collections import Counter
states = Counter(r['state'] for r in rows if r['state'].strip())
print(f"\n=== States ({len(states)}) ===")
for s, cnt in states.most_common(20):
    print(f"  {s}: {cnt:,}")

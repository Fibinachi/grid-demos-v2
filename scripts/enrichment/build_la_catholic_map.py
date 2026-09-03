"""Build LA Catholic map from GRID data + building_year for timeline."""
import sqlite3, json
from pathlib import Path
from collections import defaultdict

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

# Get ALL LA County Catholic churches with GPS
rows = db.execute("""
    SELECT c.id, c.name, c.city, c.state, c.latitude, c.longitude,
           c.building_year, c.capacity_estimate, c.source,
           t.name as tradition_name
    FROM churches c
    LEFT JOIN taxonomy t ON c.taxonomy_id = t.id
    WHERE c.county_fips_5 = '06037'
      AND c.latitude IS NOT NULL
      AND c.taxonomy_id IN (14, 86, 92, 100)
    ORDER BY c.name
""").fetchall()

churches = []
no_year = 0
year_dist = defaultdict(int)

for r in rows:
    entry = {
        'id': r['id'],
        'name': r['name'],
        'city': r['city'],
        'lat': r['latitude'],
        'lon': r['longitude'],
        'source': r['source'],
        'tradition': r['tradition_name'],
    }
    
    by = r['building_year']
    if by and by > 1800 and by < 2030:
        entry['birth'] = int(by)
        year_dist[int(by)] += 1
    else:
        # No year - assign to 1920 as placeholder or mark as unknown
        no_year += 1
        entry['birth'] = None
    
    entry['capacity'] = r['capacity_estimate']
    churches.append(entry)

print(f"Total LA Catholic churches: {len(churches)}")
print(f"With building_year: {len(churches) - no_year}")
print(f"Without building_year: {no_year}")

# Year distribution
print("\nYear distribution (top 20):")
for yr, cnt in sorted(year_dist.items(), key=lambda x: -x[1])[:20]:
    print(f"  {yr}: {cnt}")

# Year range
with_year = [c['birth'] for c in churches if c['birth']]
print(f"\nYear range: {min(with_year)} - {max(with_year)}")

# Build decade distribution for context
decades = defaultdict(int)
for y in with_year:
    decades[(y // 10) * 10] += 1
print("\nBy decade:")
for d in sorted(decades):
    print(f"  {d}s: {decades[d]} {'#' * (decades[d] // 5)}")

# Save
out_path = Path("E:/grid/data/directories/parsed/la_grid_catholic.json")
out_path.write_text(json.dumps({
    'churches': churches,
    'total': len(churches),
    'with_year': len(with_year),
    'no_year': no_year,
    'year_min': min(with_year) if with_year else None,
    'year_max': max(with_year) if with_year else None,
}, indent=2, ensure_ascii=False), encoding='utf-8')
print(f"\nSaved to {out_path}")

db.close()

"""Analyze unknowns and build DeepSeek classification batch"""
import sqlite3, os, json
from collections import Counter

db = sqlite3.connect(r'E:\grid\churches.db', timeout=60)

# Get all unknown records with their names and counts
unknowns = db.execute("""
    SELECT LOWER(name), COUNT(*) as cnt 
    FROM churches 
    WHERE (faith_tradition IS NULL OR faith_tradition = '')
    AND name != '' AND name IS NOT NULL
    GROUP BY name
    ORDER BY cnt DESC
""").fetchall()

print(f"Total unknown records: {sum(r[1] for r in unknowns):,}")
print(f"Distinct names: {len(unknowns):,}")

# Show distribution by count
count_buckets = Counter()
for name, cnt in unknowns:
    if cnt >= 10: bucket = '10+'
    elif cnt >= 5: bucket = '5-9'
    elif cnt >= 2: bucket = '2-4'
    else: bucket = '1'
    count_buckets[bucket] += 1

print(f"\nName frequency distribution:")
for b in ['10+', '5-9', '2-4', '1']:
    print(f"  {b:5s}: {count_buckets[b]:>6,} names")

# Show the most common names
print(f"\nTop 50 most common unknown names:")
for name, cnt in unknowns[:50]:
    print(f"  {name[:60]:60s} {cnt:>5,}")

# Get full records for the most common names (top 500 distinct names)
top_names = [name for name, cnt in unknowns[:500]]

# For each, get a sample record with city/state
print(f"\nSample records for top 500 names (city/state/website):")
for name in top_names[:20]:
    r = db.execute("""
        SELECT name, city, state, website FROM churches 
        WHERE LOWER(name) = ? AND (faith_tradition IS NULL OR faith_tradition = '')
        LIMIT 1
    """, (name,)).fetchone()
    if r:
        print(f"  {r[0][:55]:55s} | {r[1][:18]:18s} {r[2]:3s} | web={'Y' if r[3] else 'N':3s}")

# Save the top names to a JSON file for the classifier
names_data = []
for name, cnt in unknowns[:500]:
    r = db.execute("""
        SELECT name, city, state, website FROM churches 
        WHERE LOWER(name) = ? AND (faith_tradition IS NULL OR faith_tradition = '')
        LIMIT 1
    """, (name,)).fetchone()
    if r:
        names_data.append({
            'name': r[0],
            'city': r[1] or '',
            'state': r[2] or '',
            'has_website': bool(r[3]),
            'count': cnt,
            'id': None  # Will be populated by the classifier
        })

output_path = r'E:\grid\data\unknowns_to_classify.json'
with open(output_path, 'w') as f:
    json.dump(names_data, f, indent=2)
print(f"\nSaved {len(names_data)} names to {output_path}")
print(f"These represent {sum(d['count'] for d in names_data):,} records")

# Coverage
total_top = sum(d['count'] for d in names_data)
print(f"\nCoverage: {total_top:,} / {sum(r[1] for r in unknowns):,} records ({total_top/sum(r[1] for r in unknowns)*100:.1f}%)")

db.close()

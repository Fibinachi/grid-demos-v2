"""Assess Judaism entries sharing exact GPS coordinates within cities."""
import sqlite3, json
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Find clusters of entries at same lat/lon within same city
c.execute("""
    SELECT ROUND(latitude,5), ROUND(longitude,5), city, country, COUNT(*) as cnt,
           GROUP_CONCAT(id) as ids,
           GROUP_CONCAT(name, '||') as names,
           GROUP_CONCAT(landmark_type, '||') as types
    FROM churches 
    WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,5), ROUND(longitude,5), city, country
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
clusters = c.fetchall()
print(f"Total clusters: {len(clusters)}")
print(f"Entries in clusters: {sum(r[4] for r in clusters)}")

# Summarize by size
from collections import Counter
size_dist = Counter(r[4] for r in clusters)
print(f"\nCluster size distribution:")
for size in sorted(size_dist):
    print(f"  {size} entries: {size_dist[size]} clusters ({size*size_dist[size]} entries)")

# Show the 15 biggest clusters
print(f"\n=== Top 15 clusters ===")
for r in clusters[:15]:
    ids = list(map(int, r[5].split(',')))
    names = r[6].split('||')
    types = r[7].split('||')
    print(f"\n  {r[2]}, {r[3]} — {r[4]} entries @ ({r[0]:.5f}, {r[1]:.5f})")
    for i, (nid, nm, tp) in enumerate(zip(ids, names, types)):
        print(f"    #{nid:>8} {str(nm)[:50]:50s} [{tp or 'None'}]")

# Check what types of entries are in clusters
all_types = []
for r in clusters:
    types = r[7].split('||')
    all_types.extend(types)
type_dist = Counter(all_types)
print(f"\n=== Entry types in clusters ===")
for t, n in type_dist.most_common(20):
    print(f"  {t or 'NULL':20s} {n:>5}")

# How many clusters have at least one 'synagogue' type?
has_synagogue = 0
for r in clusters:
    types = r[7].split('||')
    if 'synagogue' in types:
        has_synagogue += 1
print(f"\nClusters with ≥1 synagogue: {has_synagogue}/{len(clusters)}")

# How many entries would be collapsed if we keep the best one per cluster?
total_in_clusters = sum(r[4] for r in clusters)
total_clusters = len(clusters)
would_delete = total_in_clusters - total_clusters
print(f"\nWould collapse: {total_in_clusters} entries into {total_clusters} primaries")
print(f"Would delete/merge: {would_delete} entries")

conn.close()

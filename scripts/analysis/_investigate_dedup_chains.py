"""
Investigate dedup map chain structure.
"""
import sqlite3, sys

conn = sqlite3.connect(r'E:\grid\churches.db')
cur = conn.cursor()

# 1. Basic counts
total = cur.execute('SELECT COUNT(*) FROM _gps_dedup_map').fetchone()[0]
distinct_dupes = cur.execute('SELECT COUNT(DISTINCT dupe_id) FROM _gps_dedup_map').fetchone()[0]
distinct_survs = cur.execute('SELECT COUNT(DISTINCT survivor_id) FROM _gps_dedup_map').fetchone()[0]
multi = cur.execute('SELECT COUNT(*) FROM (SELECT dupe_id FROM _gps_dedup_map GROUP BY dupe_id HAVING COUNT(*) > 1)').fetchone()[0]
self_ref = cur.execute('SELECT COUNT(*) FROM _gps_dedup_map WHERE dupe_id = survivor_id').fetchone()[0]
print(f'Total pairs: {total:,}')
print(f'Distinct dupes: {distinct_dupes:,}')
print(f'Distinct survivors: {distinct_survs:,}')
print(f'Duplicate dupe_ids: {multi}')
print(f'Self-references: {self_ref}')

# 2. Mutual refs
pure_surv = cur.execute('SELECT COUNT(DISTINCT survivor_id) FROM _gps_dedup_map WHERE survivor_id NOT IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
cross_ref = cur.execute('SELECT COUNT(DISTINCT survivor_id) FROM _gps_dedup_map WHERE survivor_id IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
print(f'\nPure survivors (never dupes): {pure_surv:,}')
print(f'Cross-ref survivors (also dupes): {cross_ref:,}')

# 3. Load into memory and build chain map
print('\nLoading dedup map into memory...')
rows = cur.execute('SELECT dupe_id, survivor_id FROM _gps_dedup_map').fetchall()
parent = {d: s for d, s in rows}
print(f'Loaded {len(parent):,} pairs')

# 4. Use path compression to resolve all chains
def compress(did):
    path = []
    steps = 0
    while did in parent:
        path.append(did)
        did = parent[did]
        steps += 1
        if steps > 1000000:
            return None  # cycle
    for node in path:
        parent[node] = did
    return did

# Process in batches with progress
keys = list(parent.keys())
n = len(keys)
cycle_count = 0
max_depth = 0
for i, did in enumerate(keys):
    result = compress(did)
    if result is None:
        cycle_count += 1
    if (i+1) % 50000 == 0:
        print(f'  Processed {i+1:,}/{n:,}...')

print(f'\nCycles detected: {cycle_count}')

# Now check chain depths
depth_counts = {}
for did, ult in parent.items():
    depth = 0
    s = ult
    while s in parent and depth < 1000:
        depth += 1
        s = parent[s]
    depth_counts[depth] = depth_counts.get(depth, 0) + 1

print('\nChain depth distribution (after compression):')
for d in sorted(depth_counts.keys())[:30]:
    print(f'  depth={d}: {depth_counts[d]:,}')

conn.close()

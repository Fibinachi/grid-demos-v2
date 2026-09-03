"""Find Judaism entries that share GPS locations."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Find exact coordinate duplicates
c.execute("""
    SELECT ROUND(latitude,4), ROUND(longitude,4), COUNT(*) as cnt, 
           GROUP_CONCAT(id) as ids, 
           GROUP_CONCAT(name || '|' || city || '|' || state || '|' || COALESCE(landmark_type,'?')) as details
    FROM churches 
    WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,4), ROUND(longitude,4)
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"Total coordinate clusters with 2+ entries: {len(rows)}")

total_dup_entries = sum(r[2] for r in rows)
print(f"Total entries in clusters: {total_dup_entries}")
print(f"Unique coordinates: {len(rows)}")

# Show top 20 clusters
print(f"\n=== Top 20 clusters ===")
for r in rows[:20]:
    ids = r[3].split(',')
    details = r[4].split(',')
    print(f"\n  [{r[2]} entries] lat={r[0]:.4f} lon={r[1]:.4f}")
    for i, (id_, det) in enumerate(zip(ids, details)):
        parts = det.split('|')
        name = parts[0][:50]
        city = parts[1] if len(parts) > 1 else ''
        state = parts[2] if len(parts) > 2 else ''
        ltype = parts[3] if len(parts) > 3 else '?'
        print(f"    #{id_:>8} {name:50s} {city:20s} {state:10s} [{ltype}]")

# Also check close coordinates (within ~50m)
print(f"\n\n=== Entries within ~50m of each other ===")
c.execute("""
    SELECT a.id as id1, b.id as id2,
           a.name as name1, b.name as name2,
           a.latitude, a.longitude, b.latitude, b.longitude,
           a.city, b.city, a.landmark_type as type1, b.landmark_type as type2
    FROM churches a
    JOIN churches b ON a.id < b.id
    WHERE a.faith='Judaism' AND b.faith='Judaism'
      AND a.latitude IS NOT NULL AND b.latitude IS NOT NULL
      AND ABS(a.latitude - b.latitude) < 0.001
      AND ABS(a.longitude - b.longitude) < 0.001
      AND (ROUND(a.latitude,4) != ROUND(b.latitude,4) OR ROUND(a.longitude,4) != ROUND(b.longitude,4))
    LIMIT 30
""")
for r in c.fetchall():
    print(f"\n  #{r[0]:>8} {str(r[2] or '')[:45]:45s} [{r[10]}]")
    print(f"  #{r[1]:>8} {str(r[3] or '')[:45]:45s} [{r[11]}]")
    print(f"  {r[4]:.6f},{r[5]:.6f} vs {r[6]:.6f},{r[7]:.6f}  diff={abs(r[4]-r[6])*111320:.0f}m")

conn.close()

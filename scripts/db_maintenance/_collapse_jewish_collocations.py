"""Collapse Judaism entries sharing GPS coordinates into main + ministries JSON.

Strategy:
- For each coordinate cluster of 2+ entries, identify the "main" building:
  1. Prefer 'synagogue' over other types (organization, school, etc.)
  2. Prefer 'chabad_house' over types like school
  3. Pick the shortest/cleanest name as main
- Other entries become ministries JSON on the main entry
- Delete child entries after capturing their info
- Log all provenance
"""
import sqlite3, json
from datetime import datetime

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

SOURCE = 'jewish_collapse'

# Get all coordinate clusters
c.execute("""
    SELECT ROUND(latitude,4), ROUND(longitude,4), COUNT(*) as cnt
    FROM churches 
    WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,4), ROUND(longitude,4)
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
""")
clusters = c.fetchall()
print(f"Total clusters to process: {len(clusters)}")

# Priority order for choosing the "main" entry
TYPE_PRIORITY = {
    'synagogue': 0,
    'chabad_house': 1,
    'mikveh': 2,
    'yeshiva': 3,
    'kollel': 4,
    'school': 5,
    'community_center': 6,
    'hillel': 7,
    'museum': 8,
    'cemetery': 9,
    'organization': 10,
    'retail': 11,
    'food': 12,
}

total_deleted = 0
total_ministries = 0

for lat_rounded, lon_rounded, cnt in clusters:
    c.execute("""
        SELECT id, name, city, state, country, landmark_type, tradition
        FROM churches WHERE faith='Judaism' 
        AND ROUND(latitude,4)=? AND ROUND(longitude,4)=?
        ORDER BY name
    """, (lat_rounded, lon_rounded))
    entries = c.fetchall()
    
    if len(entries) < 2:
        continue
    
    # Choose main entry: lowest type priority wins, then shortest name
    best = None
    best_priority = 999
    best_name_len = 999
    
    for e in entries:
        ltype = e[5] or 'synagogue'
        priority = TYPE_PRIORITY.get(ltype, 50)
        name_len = len(str(e[1] or ''))
        # Prefer synagogues/chabad, then shorter names
        if priority < best_priority or (priority == best_priority and name_len < best_name_len):
            best = e
            best_priority = priority
            best_name_len = name_len
    
    main_id = best[0]
    main_name = best[1]
    main_type = best[5] or 'synagogue'
    
    # Build ministries list from others
    ministries = []
    children_to_delete = []
    
    for e in entries:
        if e[0] == main_id:
            continue
        ministries.append({
            'id': e[0],
            'name': str(e[1] or ''),
            'city': str(e[2] or ''),
            'state': str(e[3] or ''),
            'type': e[5] or 'synagogue',
            'tradition': e[6] or '',
        })
        children_to_delete.append(e[0])
    
    if not ministries:
        continue
    
    # Get existing ministries JSON on main entry
    c.execute("SELECT ministries FROM churches WHERE id=?", (main_id,))
    row = c.fetchone()
    existing = json.loads(row[0]) if row and row[0] else []
    if not isinstance(existing, list):
        existing = []
    
    # Merge - don't add if same name already exists
    existing_names = {m.get('name', '') for m in existing if isinstance(m, dict)}
    new_ministries = [m for m in ministries if m['name'] not in existing_names]
    
    if new_ministries:
        all_ministries = existing + new_ministries
        c.execute("UPDATE churches SET ministries=? WHERE id=?", 
                  (json.dumps(all_ministries), main_id))
        
        # Delete children
        for child_id in children_to_delete:
            # Log provenance before delete
            c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'deleted_by_collapse', 'active', 'collapsed_into_main', ?)",
                      (child_id, SOURCE))
            c.execute("DELETE FROM churches WHERE id=?", (child_id,))
        
        total_deleted += len(children_to_delete)
        total_ministries += len(new_ministries)
        
        if len(clusters) <= 50 or cnt > 3:
            print(f"  Lat={lat_rounded:.4f} Lon={lon_rounded:.4f} [{cnt}->1]: Kept #{main_id} '{str(main_name)[:40]}' ({main_type}), "
                  f"collapsed {len(children_to_delete)} into ministries ({len(new_ministries)} new)")
    
    conn.commit()

print(f"\n=== Results ===")
print(f"Clusters processed: {len(clusters)}")
print(f"Entries deleted: {total_deleted}")
print(f"Ministries added: {total_ministries}")

# Final verification
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
remaining = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL")
with_gps = c.fetchone()[0]
print(f"Judaism entries remaining: {remaining:,} ({with_gps:,} with GPS)")

# Check if any big clusters remain
c.execute("""
    SELECT ROUND(latitude,4), ROUND(longitude,4), COUNT(*) as cnt
    FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,4), ROUND(longitude,4)
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
remaining_clusters = c.fetchall()
if remaining_clusters:
    print(f"\nRemaining clusters ({len(remaining_clusters)}):")
    for r in remaining_clusters:
        print(f"  {r[2]} entries at {r[0]:.4f},{r[1]:.4f}")

conn.close()
print("\nDone!")

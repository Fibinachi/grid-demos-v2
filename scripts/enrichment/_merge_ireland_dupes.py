"""Merge 13 duplicate Ireland records."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect, log_change

conn = connect(r'E:\grid\churches.db')

# Find duplicate name groups in Ireland
dupes = conn.execute("""
    SELECT UPPER(name), COUNT(*) as cnt
    FROM churches WHERE country='Ireland' AND name IS NOT NULL AND merged_into IS NULL
    GROUP BY UPPER(name) HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"Found {len(dupes)} duplicate groups ({sum(d[1]-1 for d in dupes)} extra records)")

merged_count = 0
for name, cnt in dupes:
    rows = conn.execute(
        "SELECT id, latitude, longitude, cra_bn, address, denomination FROM churches WHERE country='Ireland' AND UPPER(name)=? AND merged_into IS NULL ORDER BY id",
        (name,)
    ).fetchall()
    
    # Score each by data richness
    scored = []
    for r in rows:
        id_ = r[0]
        if id_ is None:
            continue
        score = 0
        if r[1] and r[2]: score += 5
        if r[3]: score += 3
        if r[4]: score += 1
        if r[5]: score += 1
        scored.append((score, id_, r))
    
    scored.sort(key=lambda x: -x[0])
    keep_id = scored[0][1]
    delete_ids = [sid for _, sid, _ in scored[1:]]
    
    print(f"\n  {name[:50]} ({cnt}x) — KEEP #{keep_id} (score={scored[0][0]})")
    
    for did in delete_ids:
        # Transfer any data the kept record might be missing
        for col in ['address', 'faith', 'denomination', 'city', 'latitude', 'longitude', 'landmark_type']:
            keep_val = conn.execute(f"SELECT {col} FROM churches WHERE id=?", (keep_id,)).fetchone()[0]
            del_val = conn.execute(f"SELECT {col} FROM churches WHERE id=?", (did,)).fetchone()[0]
            if not keep_val and del_val:
                conn.execute(f"UPDATE churches SET {col}=? WHERE id=?", (del_val, keep_id))
                log_change(conn, church_id=keep_id, field_name=col, old_value=None, new_value=del_val, source='ireland_dedup')
                print(f"    ← transferred {col} from #{did}")
        
        # Mark as merged
        conn.execute("UPDATE churches SET merged_into=? WHERE id=?", (keep_id, did))
        merged_count += 1

conn.commit()

# Remaining
remaining = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT UPPER(name) FROM churches 
        WHERE country='Ireland' AND merged_into IS NULL
        GROUP BY UPPER(name) HAVING COUNT(*) > 1
    )
""").fetchone()[0]

print(f"\n{'='*50}")
print(f"Merged: {merged_count}")
print(f"Remaining duplicates: {remaining}")
conn.close()

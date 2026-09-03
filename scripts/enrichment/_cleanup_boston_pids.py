"""
Clean up over-matched PIDs and remove duplicate entries.

Strategy:
  1. For PIDs shared by multiple churches, null out the PID on ALL except 
     the best match (prefer the one with the closest name match to the 
     property owner, or the one from boston_property_assessment source)
  2. Remove boston_property_assessment records that are exact duplicates
     of existing churches (same name + same street)
  3. Keep boston_property_assessment records that represent genuinely 
     new churches not previously in our database
"""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Load property records for reference
with open(r'E:\grid\data\boston_property_records.json') as f:
    props = {p.get('PID'): p for p in json.load(f)}

# 1. Find all PIDs shared by multiple churches
pid_groups = conn.execute("""
    SELECT boston_pid, GROUP_CONCAT(id) as ids, GROUP_CONCAT(name) as names,
           GROUP_CONCAT(source) as sources
    FROM churches
    WHERE boston_pid IS NOT NULL AND boston_pid != ''
    GROUP BY boston_pid
    HAVING COUNT(*) > 1
""").fetchall()

total_cleared = 0
kept_pids = set()

for pid, ids_str, names_str, sources_str in pid_groups:
    ids = ids_str.split(',')
    names = names_str.split(',')
    sources = sources_str.split(',')
    
    prop = props.get(pid, {})
    prop_owner = (prop.get('OWNER') or '').upper()
    
    print(f"\nPID={pid} ({len(ids)} records) Owner={prop_owner[:40]}")
    
    # Score each record for best match
    scored = []
    for id_, name, src in zip(ids, names, sources):
        name_u = name.upper()
        score = 0
        
        # +5 if from property assessment (direct match)
        if src == 'boston_property_assessment':
            score += 5
        
        # +3 if owner name appears in church name
        if prop_owner and any(word in name_u for word in prop_owner.split() if len(word) > 3):
            score += 3
        
        # +2 if same street name appears in both
        prop_st = (prop.get('ST_NAME') or '').upper()
        if prop_st and prop_st in name_u:
            score += 2
        
        # +1 if has GPS
        has_gps = conn.execute("SELECT latitude FROM churches WHERE id=?", (id_,)).fetchone()
        if has_gps and has_gps[0]:
            score += 1
        
        # -2 if name is very generic ("TRUST", "CORP", "NOMINEE")
        if any(w in name_u for w in ['TRUST ', 'CORP ', 'NOMINEE', 'REALTY', 'DEVELOPMENT']):
            score -= 2
            
        scored.append((score, id_, name, src))
    
    # Sort by score descending
    scored.sort(key=lambda x: -x[0])
    
    # Keep the best match, clear others
    best = scored[0]
    print(f"  KEEP: #{best[1]} (score={best[0]}) {best[2][:40]} [{best[3]}]")
    
    for score, id_, name, src in scored[1:]:
        print(f"  CLEAR: #{id_} (score={score}) {name[:40]} [{src}]")
        conn.execute("UPDATE churches SET boston_pid = NULL WHERE id = ?", (id_,))
        total_cleared += 1
    
    kept_pids.add(pid)

conn.commit()
print(f"\nCleared {total_cleared} over-matched PID assignments")

# 2. Check: any boston_property_assessment records that have NO boston_pid? 
# Those were imported as new entries but the PID got cleared above.
# They should be reviewed.
orphans = conn.execute("""
    SELECT id, name, boston_pid FROM churches 
    WHERE source='boston_property_assessment' AND boston_pid IS NULL
""").fetchall()
if orphans:
    print(f"\n⚠️  {len(orphans)} property assessment records have no PID (orphaned)")

# 3. Summary: count records by source
print(f"\n=== UPDATED SUMMARY ===")
sources = conn.execute("SELECT source, COUNT(*) FROM churches WHERE state='MA' AND UPPER(city)='BOSTON' GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
for s in sources:
    print(f"  {s[0] or 'NULL'}: {s[1]}")

# How many unique PIDs now?
unique_pids = conn.execute("SELECT COUNT(DISTINCT boston_pid) FROM churches WHERE boston_pid IS NOT NULL").fetchone()[0]
total_pid_records = conn.execute("SELECT COUNT(*) FROM churches WHERE boston_pid IS NOT NULL").fetchone()[0]
print(f"\nUnique PIDs: {unique_pids}")
print(f"Records with PIDs: {total_pid_records}")

conn.close()

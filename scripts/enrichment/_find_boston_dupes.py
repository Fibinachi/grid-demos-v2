"""Find duplicate Boston entries created by the import."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect
from collections import defaultdict

conn = connect(r'E:\grid\churches.db')

BOSTON_CITIES = ['BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER',
    'EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE',
    'ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY']

placeholders = ','.join('?' for _ in BOSTON_CITIES)

# 1. Exact name duplicates (same name in Boston)
print("=== EXACT NAME DUPLICATES ===")
name_dupes = conn.execute(f"""
    SELECT UPPER(name) as upper_name, COUNT(*) as cnt, 
           GROUP_CONCAT(id) as ids, GROUP_CONCAT(source) as sources,
           GROUP_CONCAT(boston_pid) as pids,
           GROUP_CONCAT(address) as addrs
    FROM churches 
    WHERE state='MA' AND UPPER(city) IN ({placeholders})
    GROUP BY UPPER(name)
    HAVING cnt > 1
    ORDER BY cnt DESC
""", BOSTON_CITIES).fetchall()

print(f"Found {len(name_dupes)} names with duplicates")
for d in name_dupes[:30]:
    ids = d[2].split(',')
    sources = d[3].split(',')
    pids = d[4].split(',')
    addrs = d[5].split(',')
    print(f"\n  {d[1]}x: {d[0][:55]}")
    for i, (id_, src, pid, addr) in enumerate(zip(ids, sources, pids, addrs)):
        print(f"    #{id_:>8} [{src:35s}] pid={pid:15s} addr={addr}")

# 2. Same boston_pid on multiple churches
print(f"\n\n=== DUPLICATE BOSTON_PIDs ===")
pid_dupes = conn.execute(f"""
    SELECT boston_pid, COUNT(*) as cnt, GROUP_CONCAT(id) as ids, 
           GROUP_CONCAT(name) as names, GROUP_CONCAT(source) as sources
    FROM churches
    WHERE boston_pid IS NOT NULL AND boston_pid != ''
    GROUP BY boston_pid
    HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"Found {len(pid_dupes)} PIDs with multiple churches")
for d in pid_dupes[:20]:
    ids = d[2].split(',')
    names = d[3].split(',')
    sources = d[4].split(',')
    print(f"\n  PID={d[0]} ({d[1]} records)")
    for i, (id_, name, src) in enumerate(zip(ids, names, sources)):
        print(f"    #{id_:>8} [{src:30s}] {name[:55]}")

# 3. Same GPS coordinates (within 0.001 deg)
print(f"\n\n=== GPS DUPLICATES (same location) ===")
gps_dupes = conn.execute(f"""
    SELECT ROUND(latitude, 3) as lat, ROUND(longitude, 3) as lon, 
           COUNT(*) as cnt, GROUP_CONCAT(id) as ids,
           GROUP_CONCAT(name) as names, GROUP_CONCAT(source) as sources
    FROM churches
    WHERE state='MA' AND UPPER(city) IN ({placeholders})
      AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude, 3), ROUND(longitude, 3)
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 30
""", BOSTON_CITIES).fetchall()

print(f"Found {len(gps_dupes)} GPS clusters with multiple churches")
for d in gps_dupes[:15]:
    ids = d[3].split(',')
    names = d[4].split(',')
    sources = d[5].split(',')
    print(f"\n  ({d[0]}, {d[1]}) — {d[2]} records")
    for i, (id_, name, src) in enumerate(zip(ids, names, sources)):
        print(f"    #{id_:>8} [{src:30s}] {name[:55]}")

# 4. Summary stats
print(f"\n\n=== SUMMARY ===")
total = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({placeholders})", BOSTON_CITIES).fetchone()[0]
with_pid = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({placeholders}) AND boston_pid IS NOT NULL", BOSTON_CITIES).fetchone()[0]
from_property = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({placeholders}) AND source='boston_property_assessment'", BOSTON_CITIES).fetchone()[0]
not_from_property = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({placeholders}) AND source != 'boston_property_assessment'", BOSTON_CITIES).fetchone()[0]
print(f"Total Boston churches: {total}")
print(f"With boston_pid: {with_pid}")
print(f"Source=boston_property_assessment: {from_property}")
print(f"Source!=boston_property_assessment: {not_from_property}")
print(f"\nName dupes: {len(name_dupes)} names")
print(f"PID dupes: {len(pid_dupes)} PIDs")
print(f"GPS dupes: {len(gps_dupes)} locations")

conn.close()

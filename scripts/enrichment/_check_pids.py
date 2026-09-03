"""Debug: check what PIDs are in the DB vs property records."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Get all PIDs from DB
db_pids = set()
for row in conn.execute("SELECT DISTINCT boston_pid FROM churches WHERE boston_pid IS NOT NULL").fetchall():
    if row[0]:
        db_pids.add(row[0])

# Get all PIDs from property records
with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

prop_pids = set()
for p in props:
    pid = p.get('PID')
    if pid:
        prop_pids.add(pid)

print(f"PIDs in DB: {len(db_pids)}")
print(f"PIDs in property records: {len(prop_pids)}")

# Check overlap
overlap = db_pids & prop_pids
only_db = db_pids - prop_pids
only_prop = prop_pids - db_pids

print(f"Overlap: {len(overlap)}")
print(f"In DB but not property records: {len(only_db)}")
if only_db:
    print(f"  Sample: {list(only_db)[:10]}")

# Sample churches with PIDs not in property records
if only_db:
    print("\nChurches with PIDs not in property records:")
    for pid in list(only_db)[:10]:
        rows = conn.execute("SELECT id, name, city, source FROM churches WHERE boston_pid = ?", (pid,)).fetchall()
        for r in rows:
            print(f"  #{r[0]}: {r[1][:50]} | {r[2]} | source={r[3]} | pid={pid}")

# What about the 93 Falmouth property?
print("\n--- 93 Falmouth / Christian Science in property records ---")
for p in props:
    if p.get('PID') in ['0401162000', '0401185000']:
        print(f"PID={p.get('PID')}: {p.get('OWNER')} | {p.get('ST_NUM')} {p.get('ST_NAME')} | {p.get('LU_DESC')}")
        # Check if it's in DB
        in_db = conn.execute("SELECT id, name, source FROM churches WHERE boston_pid = ?", (p.get('PID'),)).fetchall()
        if in_db:
            for r in in_db:
                print(f"  -> IN DB: #{r[0]}: {r[1][:60]} | source={r[2]}")
        else:
            print(f"  -> NOT in DB")

# Check what source these PID churches have
print("\n--- Source breakdown of PID churches ---")
sources = conn.execute("SELECT source, COUNT(*) FROM churches WHERE boston_pid IS NOT NULL GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
for s in sources:
    print(f"  {s[0] or 'NULL'}: {s[1]}")

conn.close()

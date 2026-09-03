"""Show detailed PID duplicates and plan cleanup."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# PID duplicates in detail
pid_dupes = conn.execute("""
    SELECT boston_pid, COUNT(*) as cnt, GROUP_CONCAT(id) as ids, 
           GROUP_CONCAT(name) as names, GROUP_CONCAT(source) as sources
    FROM churches
    WHERE boston_pid IS NOT NULL AND boston_pid != ''
    GROUP BY boston_pid
    HAVING cnt > 1
    ORDER BY cnt DESC
""").fetchall()

print(f"PID duplicates: {len(pid_dupes)}")
total_extra = sum(d[1] - 1 for d in pid_dupes)
print(f"Extra records to remove: {total_extra}")

for d in pid_dupes:
    ids = d[2].split(',')
    names = d[3].split(',')
    sources = d[4].split(',')
    print(f"\nPID={d[0]} ({d[1]} records)")
    for i, (id_, name, src) in enumerate(zip(ids, names, sources)):
        has_gps = conn.execute("SELECT latitude FROM churches WHERE id=?", (id_,)).fetchone()
        gps = f"({has_gps[0]})" if has_gps and has_gps[0] else "no gps"
        print(f"  [{i+1}] #{id_:>8} {gps:30s} [{src:35s}] {name[:60]}")
    # Suggest which to keep
    print(f"  >>> Keep: the one NOT from boston_property_assessment if it has GPS")
    print(f"  >>> Or keep: the boston_property_assessment one with most data")

conn.close()

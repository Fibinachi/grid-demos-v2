"""Check current Boston enrichment state."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Check how many have boston_pid
matched = conn.execute("SELECT COUNT(*) FROM churches WHERE boston_pid IS NOT NULL").fetchone()[0]
print(f"Churches with boston_pid: {matched}")

# Check total Boston-area churches
total = conn.execute("SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ('BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER','EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE','ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY')").fetchone()[0]
print(f"Total Boston area churches: {total}")

# Check Christian Science specifically
cs = conn.execute("SELECT id, name, faith, city, boston_pid FROM churches WHERE UPPER(name) LIKE '%CHRIST SCIENTIST%'").fetchall()
print(f"\nChristian Science records:")
for c in cs:
    print(f"  #{c[0]}: {c[1][:60]} | {c[2]} | {c[3]} | pid={c[4]}")

# Check for newly imported records from our source
new = conn.execute("SELECT COUNT(*) FROM churches WHERE source = 'boston_property_assessment'").fetchone()[0]
print(f"\nRecords with source='boston_property_assessment': {new}")

# Sample new imports
if new > 0:
    samples = conn.execute("SELECT id, name, faith, city, landmark_type, boston_pid FROM churches WHERE source = 'boston_property_assessment' LIMIT 10").fetchall()
    print("Sample new imports:")
    for s in samples:
        print(f"  #{s[0]}: {s[1][:50]} | {s[2]} | {s[3]} | {s[4]} | pid={s[5]}")

# Check church_contact_values for boston_pid
pid_vals = conn.execute("SELECT COUNT(*) FROM church_contact_values WHERE contact_type = 'boston_pid'").fetchone()[0]
print(f"\nchurch_contact_values with contact_type='boston_pid': {pid_vals}")

# Also check what PIDs are in the database
pids = conn.execute("SELECT DISTINCT boston_pid FROM churches WHERE boston_pid IS NOT NULL").fetchall()
print(f"\nUnique PIDs in DB: {len(pids)}")
print(f"Sample PIDs: {[p[0] for p in pids[:10]]}")

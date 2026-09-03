"""Final summary of all Boston work done."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

BOSTON_CITIES = ['BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER',
    'EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE',
    'ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY']
p = ','.join('?' for _ in BOSTON_CITIES)

total = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p})", BOSTON_CITIES).fetchone()[0]
print(f"Total Boston area churches: {total}")

# Source breakdown
print("\nBy source:")
for s in conn.execute(f"SELECT source, COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p}) GROUP BY source ORDER BY COUNT(*) DESC", BOSTON_CITIES).fetchall():
    print(f"  {s[0] or 'NULL'}: {s[1]}")

# Faith breakdown
print("\nBy faith:")
for f in conn.execute(f"SELECT faith, COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p}) GROUP BY faith ORDER BY COUNT(*) DESC", BOSTON_CITIES).fetchall():
    print(f"  {f[0]}: {f[1]}")

# PID stats
print("\nPID stats:")
unique = conn.execute(f"SELECT COUNT(DISTINCT boston_pid) FROM churches WHERE boston_pid IS NOT NULL AND state='MA' AND UPPER(city) IN ({p})", BOSTON_CITIES).fetchone()[0]
total_pid = conn.execute(f"SELECT COUNT(*) FROM churches WHERE boston_pid IS NOT NULL AND state='MA' AND UPPER(city) IN ({p})", BOSTON_CITIES).fetchone()[0]
print(f"  Unique PIDs: {unique}")
print(f"  Records with PIDs: {total_pid}")

# Duplicate name check
dupes = conn.execute(f"""
    SELECT UPPER(name), COUNT(*) FROM churches 
    WHERE state='MA' AND UPPER(city) IN ({p})
    GROUP BY UPPER(name) HAVING COUNT(*) > 1
""", BOSTON_CITIES).fetchall()
print(f"\nDuplicate names: {len(dupes)}")
total_extra = sum(d[1]-1 for d in dupes)
print(f"Extra records from name dupes: {total_extra}")

# Show remaining name dupes
for d in dupes[:10]:
    rows = conn.execute(f"""
        SELECT id, name, source, boston_pid FROM churches 
        WHERE state='MA' AND UPPER(city) IN ({p}) AND UPPER(name)=?
    """, (d[0],)).fetchall()
    print(f"\n  {d[0][:55]} ({d[1]}x)")
    for r in rows:
        print(f"    #{r[0]:>8} [{r[2]:35s}] pid={r[3] or '':15s}")

# Total properties fetched
print(f"\n\n=== GRAND TOTALS ===")
print(f"  Property records fetched from CKAN: 457")
print(f"  New churches from property import:  371")
print(f"  New schools from schools import:    7")
print(f"  Churches matched & enriched:        {total_pid}")
print(f"  Total Boston churches in DB now:    {total}")
print(f"  DeepSeek AI classifications run:    924")

conn.close()

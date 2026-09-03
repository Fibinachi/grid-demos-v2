"""Verify dedup results."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect
conn = connect(r'E:\grid\churches.db')

BC = ['BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER',
    'EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE',
    'ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY']
p = ','.join('?' for _ in BC)

active = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p}) AND merged_into IS NULL", BC).fetchone()[0]
merged = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p}) AND merged_into IS NOT NULL", BC).fetchone()[0]
total = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p})", BC).fetchone()[0]
remaining = conn.execute(f"""
    SELECT COUNT(*) FROM (
        SELECT UPPER(name) FROM churches 
        WHERE state='MA' AND UPPER(city) IN ({p}) AND merged_into IS NULL
        GROUP BY UPPER(name) HAVING COUNT(*) > 1
    )
""", BC).fetchone()[0]

print(f"Active (not merged): {active}")
print(f"Merged & removed:    {merged}")
print(f"Total:               {total}")
print(f"Remaining dupes:     {remaining}")

# Source breakdown
print("\nBy source (active only):")
for s in conn.execute(f"SELECT source, COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p}) AND merged_into IS NULL GROUP BY source ORDER BY COUNT(*) DESC", BC).fetchall():
    print(f"  {s[0] or 'NULL'}: {s[1]}")

conn.close()

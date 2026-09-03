"""Get current DB stats for documentation update."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect
conn = connect(r'E:\grid\churches.db')

total = conn.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
with_gps = conn.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL").fetchone()[0]
print(f"Total: {total:,}")
print(f"With GPS: {with_gps:,} ({100*with_gps/total:.1f}%)")

# Faith
print("\nFaith:")
for f in conn.execute("SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC").fetchall():
    print(f"  {f[0] or 'NULL'}: {f[1]:,}")

# Country top 20
print("\nTop countries:")
for c in conn.execute("SELECT country, COUNT(*) FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20").fetchall():
    print(f"  {c[0]}: {c[1]:,}")

# Ireland
irl = conn.execute("SELECT COUNT(*) FROM churches WHERE country='Ireland'").fetchone()[0]
print(f"\nIreland: {irl:,}")

# Boston area
bc = ['BOSTON','ALLSTON','BRIGHTON','CHARLESTOWN','DORCHESTER','EAST BOSTON','HYDE PARK','JAMAICA PLAIN','MATTAPAN','READVILLE','ROSLINDALE','ROXBURY','ROXBURY CROSSING','SOUTH BOSTON','WEST ROXBURY']
p = ','.join('?' for _ in bc)
ba = conn.execute(f"SELECT COUNT(*) FROM churches WHERE state='MA' AND UPPER(city) IN ({p})", bc).fetchone()[0]
print(f"Boston area: {ba:,}")

# Source breakdown
print("\nSource:")
for s in conn.execute("SELECT source, COUNT(*) FROM churches WHERE source IS NOT NULL AND source != '' GROUP BY source ORDER BY COUNT(*) DESC LIMIT 15").fetchall():
    print(f"  {s[0]}: {s[1]:,}")

conn.close()

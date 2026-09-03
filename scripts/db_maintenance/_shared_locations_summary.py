"""Quick summary of shared locations among Judaism entries."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Basic counts
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL")
with_gps = c.fetchone()[0]
c.execute("SELECT COUNT(DISTINCT ROUND(latitude,5)||','||ROUND(longitude,5)) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL")
unique_locs = c.fetchone()[0]
c.execute("""SELECT COUNT(*) FROM (SELECT ROUND(latitude,5) as rlat, ROUND(longitude,5) as rlon FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL GROUP BY rlat, rlon HAVING COUNT(*) > 1)""")
shared_groups = c.fetchone()[0]
c.execute("""SELECT SUM(cnt) FROM (SELECT COUNT(*) as cnt FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL GROUP BY ROUND(latitude,5), ROUND(longitude,5) HAVING COUNT(*) > 1)""")
shared_entries = c.fetchone()[0] or 0

print(f"=== Judaism Location Sharing Summary ===")
print(f"Total Judaism entries with GPS: {with_gps:,}")
print(f"Unique GPS locations:          {unique_locs:,}")
print(f"")
print(f"Locations with >1 entry:      {shared_groups:,}")
print(f"Total entries sharing a loc:  {shared_entries:,}")
print(f"Potential extra congregations: {shared_entries - shared_groups:,}")
print(f"")
print(f"So ~{shared_entries:,} entries ({shared_entries/with_gps*100:.1f}%) share coordinates with another entry")
print(f"Unique physical buildings:    ~{unique_locs:,}")
print(f"")

# Top 10 shared location groups
c.execute("""
    SELECT ROUND(latitude,5)||', '||ROUND(longitude,5), city, state, country, COUNT(*) as cnt,
           GROUP_CONCAT(DISTINCT landmark_type) as types
    FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY ROUND(latitude,5), ROUND(longitude,5)
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
print("Top 10 shared-location clusters:")
for r in c.fetchall():
    print(f"  {r[4]:>3} entries at {r[0]} — {r[1]}, {r[2]}, {r[3]}  [{r[5]}]")

# Type breakdown of shared entries
c.execute("""
    WITH dups AS (
        SELECT ROUND(latitude,5) as rlat, ROUND(longitude,5) as rlon
        FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY rlat, rlon HAVING COUNT(*) > 1
    )
    SELECT c.landmark_type, COUNT(*) as cnt
    FROM churches c JOIN dups d ON ROUND(c.latitude,5)=d.rlat AND ROUND(c.longitude,5)=d.rlon
    WHERE c.faith='Judaism' GROUP BY c.landmark_type ORDER BY cnt DESC
""")
print(f"\nTypes in shared locations:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>6,}")

# Address-based sharing
c.execute("""
    SELECT COUNT(*) FROM (
        SELECT city, state, country, address, COUNT(*) as cnt
        FROM churches WHERE faith='Judaism' AND address IS NOT NULL AND address != ''
        GROUP BY city, state, country, address HAVING cnt > 1
    )
""")
addr_shared = c.fetchone()[0]
c.execute("""
    SELECT SUM(cnt) FROM (
        SELECT COUNT(*) as cnt FROM churches WHERE faith='Judaism' AND address IS NOT NULL AND address != ''
        GROUP BY city, state, country, address HAVING cnt > 1
    )
""")
addr_entries = c.fetchone()[0] or 0

print(f"\n=== Address-based sharing ===")
print(f"Groups sharing same address: {addr_shared}")
print(f"Total entries sharing address: {addr_entries}")

conn.close()

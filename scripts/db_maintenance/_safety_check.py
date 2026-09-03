"""Safety check before collapse - count entries with contacts."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Count entries in clusters
c.execute("""
    SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND id IN (
        SELECT id FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude,4), ROUND(longitude,4) HAVING COUNT(*) > 1
    )
""")
in_clusters = c.fetchone()[0]
print(f"Entries in coordinate clusters: {in_clusters:,}")

# Of those, how many have contact values?
c.execute("""
    SELECT COUNT(DISTINCT c.id) FROM churches c
    JOIN church_contact_values cv ON c.id = cv.church_id
    WHERE c.faith='Judaism' AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
    AND c.id IN (
        SELECT id FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude,4), ROUND(longitude,4) HAVING COUNT(*) > 1
    )
""")
with_contacts = c.fetchone()[0]
print(f"Entries in clusters WITH contacts: {with_contacts:,}")

# What types are in clusters?
c.execute("""
    SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
    AND id IN (
        SELECT id FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY ROUND(latitude,4), ROUND(longitude,4) HAVING COUNT(*) > 1
    )
    GROUP BY landmark_type ORDER BY COUNT(*) DESC
""")
print(f"\nType distribution in clusters:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>6,}")

# Total
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
print(f"\nTotal Judaism worldwide: {total:,}")
print(f"After collapse would be approx: {total - in_clusters + len(set())}")

conn.close()

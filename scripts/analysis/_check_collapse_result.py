"""Check overall state after collapse."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
print(f"Total Judaism: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE merged_into IS NOT NULL")
merged = c.fetchone()[0]
print(f"Merged into primary: {merged:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE merged_into IS NULL AND faith='Judaism'")
print(f"Primary entries: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE ministries IS NOT NULL")
print(f"With ministries JSON: {c.fetchone()[0]:,}")

# Sum of all ministries entries
c.execute("SELECT SUM(json_array_length(ministries)) FROM churches WHERE ministries IS NOT NULL")
total_min = c.fetchone()[0]
print(f"Total ministries stored in JSON: {total_min:,}")

# Check by landmark_type
c.execute("SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND merged_into IS NULL GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print(f"\nPrimary entries by type:")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>5,}")

# Total clusters
c.execute("""
    SELECT COUNT(*) FROM (
        SELECT ROUND(latitude,5), ROUND(longitude,5), city, country
        FROM churches WHERE faith='Judaism' AND latitude IS NOT NULL
        GROUP BY ROUND(latitude,5), ROUND(longitude,5), city, country
        HAVING COUNT(*) > 1
    )
""")
remaining_clusters = c.fetchone()[0]
print(f"\nRemaining shared-location clusters: {remaining_clusters}")

# Check if any still have merged_into but also merged_into pointing to merged entries
c.execute("""
    SELECT COUNT(*) FROM churches s
    JOIN churches p ON s.merged_into = p.id
    WHERE p.merged_into IS NOT NULL
""")
bad = c.fetchone()[0]
if bad:
    print(f"\n⚠ {bad} entries have merged_into pointing to another merged entry (chain)!")
else:
    print(f"\nNo chains — all merged_into point to primaries.")

conn.close()

"""Check church_enrichment state for MX churches."""
import sqlite3

db = sqlite3.connect("churches.db")

# Check total counts
cur = db.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN ce.rowid IS NOT NULL THEN 1 ELSE 0 END) as has_enrichment
    FROM churches ch
    LEFT JOIN church_enrichment ce ON ch.id = ce.church_id
    WHERE ch.country = 'MX'
""")
r = cur.fetchone()
print(f"Total MX churches: {r[0]}")
print(f"With church_enrichment row: {r[1]}")

# Check actual enrichment rows
cur = db.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    JOIN churches ch ON ch.id = ce.church_id 
    WHERE ch.country = 'MX'
""")
print(f"MX church_enrichment rows: {cur.fetchone()[0]}")

# Check mx_division_id population
cur = db.execute("""
    SELECT mx_division_id, mx_division_name, mx_admin_level, mx_admin_subtype
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country = 'MX' AND mx_division_id IS NOT NULL
    LIMIT 10
""")
rows = cur.fetchall()
print(f"\nMX enrichment with mx_division_id set: {len(rows)}")
for r in rows:
    print(f"  id={r[0]} name={r[1]} level={r[2]} subtype={r[3]}")

# Check if shapefile NOMGEO exists for the top matched
cur = db.execute("""
    SELECT mx_division_id, mx_division_name, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country = 'MX' AND mx_division_id IS NOT NULL
    GROUP BY mx_division_id
    ORDER BY cnt DESC
    LIMIT 10
""")
print("\nTop matched (if any):")
for r in cur.fetchall():
    print(f"  {r[1] or '(unnamed)'} ({r[0]}): {r[2]}")

db.close()

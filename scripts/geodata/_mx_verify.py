"""Verify MX pipeline results."""
import sqlite3

db = sqlite3.connect("churches.db")

cur = db.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id IS NOT NULL
""")
print("MX churches with mx_division_id set:", cur.fetchone()[0])

cur = db.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX'
""")
print("Total MX church_enrichment rows:", cur.fetchone()[0])

# Check division names
cur = db.execute("""
    SELECT mx_division_name, mx_division_id, COUNT(*) as cnt 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id IS NOT NULL 
    GROUP BY ce.mx_division_id 
    ORDER BY cnt DESC LIMIT 5
""")
print("\nTop 5 municipios by church count:")
for r in cur.fetchall():
    print(f"  {r[0]} ({r[1]}): {r[2]}")

# Check census table
cur = db.execute("SELECT COUNT(*) FROM municipio_census_mx")
print(f"\nmunicipio_census_mx rows: {cur.fetchone()[0]}")
cur = db.execute("SELECT full_id, municipio_name, total_pop FROM municipio_census_mx ORDER BY total_pop DESC LIMIT 5")
print("Top 5 by population:")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]}: {r[2]:,}")

# Check if church_enrichment has mx fields
cur = db.execute("PRAGMA table_info(church_enrichment)")
print("\nchurch_enrichment columns:")
for r in cur.fetchall():
    print(f"  {r[1]} ({r[2]})")

db.close()

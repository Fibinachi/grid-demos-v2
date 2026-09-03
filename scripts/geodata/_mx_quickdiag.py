"""Quick diagnostic for mx_division_id distribution."""
import sqlite3

db = sqlite3.connect("churches.db")

# Total CE rows
cur = db.execute("SELECT COUNT(*) FROM church_enrichment")
print(f"Total CE rows: {cur.fetchone()[0]:,}")

# MX churches with CE rows
cur = db.execute("SELECT COUNT(*) FROM church_enrichment ce WHERE EXISTS (SELECT 1 FROM churches ch WHERE ch.id=ce.church_id AND ch.country='MX')")
print(f"MX churches with CE row: {cur.fetchone()[0]:,}")

# MX CE rows grouped by whether mx_division_id is set
cur = db.execute("""
    SELECT 
        CASE WHEN ce.mx_division_id IS NOT NULL AND ce.mx_division_id != '' THEN 'has_id' ELSE 'no_id' END as grp,
        COUNT(*) as cnt
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX'
    GROUP BY grp
""")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# Sample some has_id
cur = db.execute("""
    SELECT ce.mx_division_id, ce.mx_division_name 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id IS NOT NULL AND ce.mx_division_id != ''
    LIMIT 5
""")
print(f"\nSample with mx_division_id:")
for r in cur.fetchall():
    print(f"  id='{r[0]}' name='{r[1]}'")

# Check if any have garbage values
cur = db.execute("""
    SELECT DISTINCT ce.mx_division_id 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id IS NOT NULL AND ce.mx_division_id != ''
    ORDER BY ce.mx_division_id
    LIMIT 10
""")
print(f"\nDistinct non-empty mx_division_id values (first 10):")
for r in cur.fetchall():
    print(f"  '{r[0]}'")

# Check if any are 'nannan' or similar
cur = db.execute("""
    SELECT COUNT(*) 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id = 'nannan'
""")
print(f"\nRows with 'nannan': {cur.fetchone()[0]:,}")

cur = db.execute("""
    SELECT COUNT(*) 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND ce.mx_division_id IS NOT NULL AND LENGTH(ce.mx_division_id) != 5
""")
print(f"Rows with non-5-char mx_division_id: {cur.fetchone()[0]:,}")

db.close()

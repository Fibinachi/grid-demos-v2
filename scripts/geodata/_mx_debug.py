"""Debug: check why UPDATE results don't match."""
import sqlite3

db = sqlite3.connect("churches.db")

# Direct count of all church_enrichment rows
cur = db.execute("SELECT COUNT(*) FROM church_enrichment")
print(f"Total church_enrichment rows: {cur.fetchone()[0]}")

# MX churches
cur = db.execute("SELECT COUNT(*) FROM churches WHERE country='MX'")
print(f"Total MX churches: {cur.fetchone()[0]}")

# MX church_enrichment rows
cur = db.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    WHERE EXISTS (SELECT 1 FROM churches ch WHERE ch.id = ce.church_id AND ch.country='MX')
""")
print(f"MX church_enrichment rows: {cur.fetchone()[0]}")

# With mx_division_id set
cur = db.execute("""
    SELECT COUNT(*) FROM church_enrichment ce 
    WHERE EXISTS (SELECT 1 FROM churches ch WHERE ch.id = ce.church_id AND ch.country='MX')
    AND ce.mx_division_id IS NOT NULL AND ce.mx_division_id != ''
""")
print(f"MX church_enrichment with mx_division_id: {cur.fetchone()[0]}")

# Check if some mx_division_id values are empty strings
cur = db.execute("""
    SELECT ce.mx_division_id, COUNT(*) 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX'
    GROUP BY ce.mx_division_id IS NULL OR ce.mx_division_id = ''
""")
for r in cur.fetchall():
    print(f"  mx_division_id group: {r[0]} -> count={r[1]}")

# Check the sample
cur = db.execute("""
    SELECT mx_division_id, mx_division_name 
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX' AND mx_division_id IS NOT NULL AND mx_division_id != ''
    LIMIT 5
""")
print("\nSample geocoded rows:")
for r in cur.fetchall():
    print(f"  div_id='{r[0]}' name='{r[1]}'")

# Check empty mx_division_id values
cur = db.execute("""
    SELECT ce.mx_division_id, ce.mx_admin_level, ce.mx_admin_subtype
    FROM church_enrichment ce 
    JOIN churches ch ON ch.id=ce.church_id 
    WHERE ch.country='MX'
    LIMIT 10
""")
print("\nAny rows (first 10):")
for r in cur.fetchall():
    print(f"  div_id='{r[0]}' level={r[1]} subtype='{r[2]}'")

db.close()

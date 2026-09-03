"""Detailed assessment of Muslim classification gap."""
import sqlite3
conn = sqlite3.connect("churches.db")
c = conn.cursor()

# How were the existing traditions set?
print("=== Tradition sources for Islam ===")
c.execute("""
    SELECT muslim_classification_source, COUNT(*) as cnt
    FROM churches WHERE faith='Islam' AND muslim_classification_source IS NOT NULL
    GROUP BY muslim_classification_source
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {str(r[0] or 'N/A'):35s}: {r[1]:>8,}")

# Check if tradition matches muslim_affiliation
print("\n=== Tradition vs muslim_affiliation overlap ===")
c.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN tradition IS NOT NULL AND tradition != '' THEN 1 ELSE 0 END) as has_tradition,
        SUM(CASE WHEN muslim_affiliation IS NOT NULL AND muslim_affiliation != '' THEN 1 ELSE 0 END) as has_muslim_aff,
        SUM(CASE WHEN tradition IS NOT NULL AND muslim_affiliation IS NOT NULL THEN 1 ELSE 0 END) as both,
        SUM(CASE WHEN tradition IS NULL AND muslim_affiliation IS NULL THEN 1 ELSE 0 END) as neither
    FROM churches WHERE faith='Islam'
""")
r = c.fetchone()
print(f"  Total Islam: {r[0]:,}")
print(f"  Has tradition: {r[1]:,}")
print(f"  Has muslim_affiliation: {r[2]:,}")
print(f"  Both: {r[3]:,}")
print(f"  Neither (gap): {r[4]:,}")

# What's in the gap?
print("\n=== Gap samples (no tradition, no muslim_affiliation) ===")
c.execute("""
    SELECT id, name, city, state, country FROM churches 
    WHERE faith='Islam' AND (tradition IS NULL OR tradition='') 
      AND (muslim_affiliation IS NULL OR muslim_affiliation='')
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  ID={r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {str(r[2] or ''):20s} {r[3] or ''} | {r[4] or ''}")

# Country breakdown of gap
print("\n=== Gap by country (top 20) ===")
c.execute("""
    SELECT country, COUNT(*) as cnt FROM churches 
    WHERE faith='Islam' AND (tradition IS NULL OR tradition='') 
      AND (muslim_affiliation IS NULL OR muslim_affiliation='')
    GROUP BY country ORDER BY cnt DESC LIMIT 20
""")
for r in c.fetchall():
    print(f"  {str(r[0] or 'NULL'):20s}: {r[1]:>8,}")

# Check the FLTD restructuring
print("\n=== How were existing traditions assigned? ===")
c.execute("""
    SELECT tradition, COUNT(*) as cnt,
           ROUND(AVG(muslim_confidence), 3) as avg_conf
    FROM churches WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''
    GROUP BY tradition ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {str(r[0]):25s}: {r[1]:>8,} | avg_conf={r[2]}")

conn.close()

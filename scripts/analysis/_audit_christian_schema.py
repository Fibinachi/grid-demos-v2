"""Audit Christian data schema and enrichment state."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

print("=== CHURCHES TABLE COLUMNS ===")
c = db.execute('PRAGMA table_info(churches)')
for col in c.fetchall():
    print(f"  {col[1]}: {col[2]}")

print("\n=== CHURCH_ENRICHMENT COLUMNS ===")
c = db.execute('PRAGMA table_info(church_enrichment)')
for col in c.fetchall():
    print(f"  {col[1]}: {col[2]}")

print("\n=== CHRISTIAN RECORDS IN church_enrichment ===")
c = db.execute("""
    SELECT COUNT(*) FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian'
""")
print(f"  {c.fetchone()[0]:,}")

print("\n=== ENRICHMENT DENOMINATION DISTRIBUTION (top 30) ===")
c = db.execute("""
    SELECT e.denomination, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' AND e.denomination IS NOT NULL AND e.denomination != '' 
    GROUP BY e.denomination ORDER BY cnt DESC LIMIT 30
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== CHURCHES WITH NULL DENOM BUT ENRICHMENT HAS DENOM ===")
c = db.execute("""
    SELECT COUNT(*) FROM churches c 
    JOIN church_enrichment e ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    AND (c.denomination IS NULL OR c.denomination = '')
    AND e.denomination IS NOT NULL AND e.denomination != ''
""")
print(f"  {c.fetchone()[0]:,}")

print("\n=== CHURCHES WHERE BOTH DENOMS ARE NULL ===")
c = db.execute("""
    SELECT COUNT(*) FROM churches c 
    LEFT JOIN church_enrichment e ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    AND (c.denomination IS NULL OR c.denomination = '')
    AND (e.denomination IS NULL OR e.denomination = '' OR e.church_id IS NULL)
""")
print(f"  {c.fetchone()[0]:,}")

print("\n=== SOURCE ANALYSIS FOR NULL-DENOM CHRISTIAN RECORDS ===")
c = db.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches 
    WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
    GROUP BY source ORDER BY cnt DESC LIMIT 20
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== LANDMARK_TYPE DISTRIBUTION (Christian, NULL denom) ===")
c = db.execute("""
    SELECT COALESCE(landmark_type, 'NULL') as lt, COUNT(*) as cnt 
    FROM churches 
    WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
    GROUP BY lt ORDER BY cnt DESC LIMIT 20
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== NAME PATTERNS FOR NULL-DENOM CHRISTIANS (sample) ===")
c = db.execute("""
    SELECT name, landmark_type, source, country 
    FROM churches 
    WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')
    AND name IS NOT NULL AND name != ''
    LIMIT 50
""")
for row in c.fetchall():
    print(f"  {row[0][:60]:60s} | {str(row[1] or '')[:20]:20s} | {str(row[2] or '')[:25]:25s} | {row[3] or ''}")

db.close()

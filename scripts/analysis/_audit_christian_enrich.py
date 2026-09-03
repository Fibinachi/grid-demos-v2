"""Audit Christian enrichment data in detail."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

print("=== LITURGICAL FAMILY for Christians ===")
c = db.execute("""
    SELECT COALESCE(e.liturgical_family, 'NULL') as lf, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    GROUP BY lf ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== LITURGICAL TRADITION for Christians ===")
c = db.execute("""
    SELECT COALESCE(e.liturgical_tradition, 'NULL') as lt, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    GROUP BY lt ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== DENOM_SUBGROUP for Christians ===")
c = db.execute("""
    SELECT COALESCE(e.denom_subgroup, 'NULL') as dsg, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    GROUP BY dsg ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== DENOM_REGION for Christians ===")
c = db.execute("""
    SELECT COALESCE(e.denom_region, 'NULL') as dr, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    GROUP BY dr ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== CATHOLIC HIERARCHY DATA ===")
c = db.execute("""
    SELECT COALESCE(e.rite, 'NULL') as rite, COUNT(*) as cnt 
    FROM church_enrichment e 
    JOIN churches c ON e.church_id = c.id 
    WHERE c.faith = 'Christian' 
    GROUP BY rite ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== EXISTING CLASSIFICATION FILES FOR CHRISTIAN DENOMS ===")
import glob
christian_scripts = []
for s in sorted(glob.glob('_classify_*.py')):
    with open(s, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read(500)
        if 'christian' in content.lower() or 'catholic' in content.lower() or 'denomination' in content.lower():
            christian_scripts.append((s, content[:200].replace('\n', ' ')))
for name, preview in christian_scripts:
    print(f"\n--- {name} ---")
    print(f"  {preview}")

db.close()

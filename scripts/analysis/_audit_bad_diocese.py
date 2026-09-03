"""Root cause: wrong diocese assignments."""
import sqlite3, csv
conn = sqlite3.connect('churches.db')
c = conn.cursor()

# 1. Where do diocese names come from?
print("=== Diocese name sources ===")
c.execute("""
    SELECT CASE 
        WHEN ce.diocese LIKE 'Diocese of%' OR ce.diocese LIKE 'Archdiocese%' THEN 'Burchfiel mapper'
        WHEN ce.diocese LIKE '%[%' THEN 'Eastern Rite (multi-state OK)'
        ELSE 'Generic/ambiguous name'
    END as source_type,
    COUNT(DISTINCT ce.diocese) as dioceses, COUNT(*) as churches
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
    GROUP BY 1
""")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:>4} names, {r[2]:>7,} churches")

# 2. Generic names with wrong-state spread
print("\n=== Generic name spread (likely wrong) ===")
c.execute("""
    SELECT ce.diocese, COUNT(DISTINCT ch.state) as states, COUNT(*) as churches
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese NOT LIKE 'Diocese of%' AND ce.diocese NOT LIKE 'Archdiocese%'
      AND ce.diocese NOT LIKE '%[%'
    GROUP BY ce.diocese HAVING COUNT(DISTINCT ch.state) > 2
    ORDER BY states DESC LIMIT 20
""")
for r in c.fetchall():
    print(f"  {r[0]:40s} {r[1]:>3} states, {r[2]:>6,}")

# 3. LA in SC - check fips
print("\n=== LA diocese in SC ===")
for r in c.execute("SELECT ch.id,ch.name,ch.city,ch.state,ch.fips,ce.diocese,ch.denomination FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id WHERE ch.state='SC' AND ce.diocese='Los Angeles'"):
    print(f"  id={r[0]} {str(r[1]):40s} {r[4]} city={r[3]}")

# 4. Atlanta in FL
print("\n=== Atlanta in FL ===")
for r in c.execute("SELECT ch.id,ch.name,ch.city,ch.state,ch.fips,ce.diocese FROM church_enrichment ce JOIN churches ch ON ch.id=ce.church_id WHERE ch.state='FL' AND ce.diocese='Atlanta'"):
    print(f"  id={r[0]} {str(r[1]):40s} fips={r[4]} diocese={r[5]}")

# 5. Check Burchfiel CSV for "Los Angeles"
print("\n=== 'Los Angeles' in Burchfiel CSV ===")
with open('data/diocese_mapper/counties_by_diocese.csv','r') as f:
    for row in csv.DictReader(f):
        if 'Los Angeles' in row.get('Diocese',''):
            print(f"  GEOID={row['GEOID']} County={row['NAME']} State={row['State_Code']} Diocese={row['Diocese']}")
            break

# 6. Count: how many generic diocese names from Burchfiel vs pre-existing
print("\n=== Count by diocese name format ===")
c.execute("""
    SELECT ce.diocese, ch.state, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches ch ON ch.id = ce.church_id
    WHERE ch.country='US' AND ce.diocese IS NOT NULL AND ce.diocese != ''
      AND (LOWER(ch.denomination) LIKE '%catholic%' OR LOWER(ch.denomination) LIKE '%roman%')
      AND ce.diocese NOT LIKE 'Diocese of%' AND ce.diocese NOT LIKE 'Archdiocese%'
      AND ce.diocese NOT LIKE '%[%'
    GROUP BY 1, 2
    HAVING cnt > 5
    ORDER BY cnt DESC LIMIT 30
""")
print("\nTop (diocese, state) combos for generic names:")
for r in c.fetchall():
    print(f"  {r[0]:35s} in {r[1]:5s} -> {r[2]:>5,}")

conn.close()

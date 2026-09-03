"""Check existing school records in churches, merge_target status, and diocese connectivity"""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
db.row_factory = sqlite3.Row
cur = db.cursor()

# 1. la_catholic_schools source
cur.execute("""
    SELECT source, COUNT(*) as cnt, 
           SUM(CASE WHEN landmark_type = 'school' THEN 1 ELSE 0 END) as tagged_school,
           SUM(CASE WHEN landmark_type IS NULL OR landmark_type = '' THEN 1 ELSE 0 END) as null_lm,
           SUM(CASE WHEN landmark_type = 'church' THEN 1 ELSE 0 END) as tagged_church
    FROM churches
    WHERE source LIKE '%la_catholic_schools%'
    GROUP BY source
""")
print("=== LA CATHOLIC SCHOOLS SOURCE ===")
for r in cur.fetchall():
    print(f"  {r['source']}: {r['cnt']} total, {r['tagged_school']} school, {r['null_lm']} null, {r['tagged_church']} church")
print()

# 2. Check merge_target pss_schools in churches
cur.execute("""
    SELECT COUNT(*) as cnt,
           SUM(CASE WHEN c.landmark_type = 'school' THEN 1 ELSE 0 END) as tagged_school,
           SUM(CASE WHEN c.landmark_type IS NULL OR c.landmark_type = '' THEN 1 ELSE 0 END) as null_lm,
           SUM(CASE WHEN c.landmark_type = 'church' THEN 1 ELSE 0 END) as tagged_church
    FROM pss_schools ps
    JOIN churches c ON ps.merge_target_id = c.id
""")
print("=== PSS SCHOOLS MERGE TARGET STATUS IN CHURCHES ===")
r = cur.fetchone()
print(f"  {r['cnt']} total, {r['tagged_school']} school, {r['null_lm']} null, {r['tagged_church']} church")

# Sample merge-targeted schools
cur.execute("""
    SELECT c.name, c.landmark_type, c.denomination, ps.pinst, ps.diocese, ps.relig_label
    FROM pss_schools ps
    JOIN churches c ON ps.merge_target_id = c.id
    WHERE c.landmark_type IS NULL OR c.landmark_type = ''
    LIMIT 20
""")
print("\nSample merge_target records with null landmark_type:")
for r in cur.fetchall():
    print(f"  {r['name'][:50]:50s} | lm={str(r['landmark_type'] or 'NULL'):15s} | pss={r['pinst'][:40]:40s} | diocese={r['diocese'] or ''}")

cur.execute("""
    SELECT c.name, c.landmark_type, c.denomination, ps.pinst, ps.diocese, ps.relig_label
    FROM pss_schools ps
    JOIN churches c ON ps.merge_target_id = c.id
    WHERE c.landmark_type = 'church'
    LIMIT 20
""")
print("\nSample merge_target records with landmark_type='church':")
for r in cur.fetchall():
    print(f"  {r['name'][:50]:50s} | lm={str(r['landmark_type'] or 'NULL'):15s} | pss={r['pinst'][:40]:40s} | diocese={r['diocese'] or ''}")
print()

# 3. Check how many pss_schools do NOT have merge targets yet
cur.execute("SELECT COUNT(*) FROM pss_schools WHERE merge_target_id IS NULL")
cnt = cur.fetchone()[0]
print(f"pss_schools WITHOUT merge_target: {cnt} / {cur.execute('SELECT COUNT(*) FROM pss_schools').fetchone()[0]}")

# 4. Now let's get a full picture of existing diocese data in church_enrichment
cur.execute("""
    SELECT COUNT(*) as cnt,
           SUM(CASE WHEN diocese IS NOT NULL AND diocese != '' THEN 1 ELSE 0 END) as has_diocese
    FROM church_enrichment
    WHERE church_id IN (SELECT id FROM churches WHERE landmark_type = 'school')
""")
print("\n=== SCHOOLS WITH DIOCESE IN church_enrichment ===")
r = cur.fetchone()
print(f"  Schools in enrichment: {r['cnt']}, with diocese: {r['has_diocese']}")

# 5. Count total schools in DB (landmark_type=school)
cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'school'")
school_count = cur.fetchone()[0]
print(f"\n=== CURRENT SCHOOL COUNTS ===")
print(f"  Total landmark_type='school': {school_count}")

# 6. Check what other school-related landmark types exist
cur.execute("SELECT DISTINCT landmark_type FROM churches WHERE landmark_type LIKE '%school%' OR landmark_type LIKE '%university%' OR landmark_type LIKE '%college%'")
print("School-related landmark types:")
for r in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM churches WHERE landmark_type = '{r[0]}'")
    print(f"  {r[0]}: {cur.fetchone()[0]}")

# 7. Check the church_enrichment diocese field for existing schools
cur.execute("""
    SELECT ce.diocese, COUNT(*) as cnt
    FROM church_enrichment ce
    JOIN churches c ON ce.church_id = c.id
    WHERE c.landmark_type = 'school'
      AND ce.diocese IS NOT NULL AND ce.diocese != ''
    GROUP BY ce.diocese
    ORDER BY cnt DESC
    LIMIT 20
""")
print("\n=== EXISTING SCHOOL DIOCESE ASSIGNMENTS (from enrichment) ===")
for r in cur.fetchall():
    print(f"  {r['diocese'][:50]:50s} {r['cnt']}")

# 8. How many schools might be connectable via FIPS + county_diocese_map?
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM churches c
    LEFT JOIN church_enrichment ce ON c.id = ce.church_id
    WHERE c.landmark_type = 'school'
      AND (ce.diocese IS NULL OR ce.diocese = '')
""")
r = cur.fetchone()
print(f"\nSchools without diocese in enrichment: {r['cnt']}")

db.close()

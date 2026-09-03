"""Deep audit: school diocese data, pss_schools connection, and classification patterns"""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
db.row_factory = sqlite3.Row
cur = db.cursor()

# 1. pss_schools diocese breakdown
print("=== PSS SCHOOLS DIOCESE BREAKDOWN (top 50) ===")
cur.execute("""
    SELECT diocese, COUNT(*) as cnt
    FROM pss_schools
    WHERE diocese IS NOT NULL AND diocese != ''
    GROUP BY diocese
    ORDER BY cnt DESC
    LIMIT 50
""")
rows = cur.fetchall()
total_with_diocese = sum(r['cnt'] for r in cur.execute("SELECT COUNT(*) as cnt FROM pss_schools WHERE diocese IS NOT NULL AND diocese != ''").fetchall())
total_schools = cur.execute("SELECT COUNT(*) FROM pss_schools").fetchone()[0]
print(f"Total pss_schools: {total_schools}, with diocese: {total_with_diocese}")
for r in rows:
    print(f"  {r['diocese'][:50]:50s} {r['cnt']}")
print()

# 2. Check relig/orient breakdown
print("=== PSS SCHOOLS RELIGION BREAKDOWN (top 40) ===")
cur.execute("""
    SELECT relig_label, COUNT(*) as cnt
    FROM pss_schools
    GROUP BY relig_label
    ORDER BY cnt DESC
    LIMIT 40
""")
for r in cur.fetchall():
    print(f"  {str(r['relig_label'])[:60]:60s} {r['cnt']}")
print()

print("=== PSS SCHOOLS ORIENTATION BREAKDOWN (top 30) ===")
cur.execute("""
    SELECT orient_label, COUNT(*) as cnt
    FROM pss_schools
    GROUP BY orient_label
    ORDER BY cnt DESC
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  {str(r['orient_label'])[:60]:60s} {r['cnt']}")
print()

# 3. Sample pss_schools rows to understand data
print("=== PSS SCHOOLS SAMPLE (10 rows) ===")
cur.execute("SELECT * FROM pss_schools LIMIT 10")
for r in cur.fetchall():
    print(dict(r))
print()

# 4. Now look at churches with landmark_type='school' - are they already linked?
print("=== CHURCHES WITH landmark_type='school': key fields ===")
cur.execute("""
    SELECT name, denomination, faith, source, ein, osm_id, city, state, country
    FROM churches
    WHERE landmark_type = 'school'
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | {str(r['denomination'] or '')[:25]} | {str(r['source'] or ''):20s} | {r['city'] or ''}")
print()

cur.execute("SELECT COUNT(*) as cnt FROM churches WHERE landmark_type = 'school'")
cnt = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) as cnt FROM churches WHERE landmark_type = 'school' AND country = 'US'")
us_cnt = cur.fetchone()[0]
print(f"  Total landmark_type=school: {cnt}, US: {us_cnt}")
print()

# 5. What existing "school" records look like - are they actual schools or churches with school buildings?
print("=== SCHOOL LANDMARK TYPE - Denomination breakdown ===")
cur.execute("""
    SELECT COALESCE(faith, 'NULL') as f, COUNT(*) as cnt
    FROM churches
    WHERE landmark_type = 'school'
    GROUP BY f
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f"  {r['f']:20s} {r['cnt']}")
print()

# 6. Check what landmark_type should be 'school' but isn't
# Focus on records with "School" or "Academy" in name but landmark_type='church'
print("=== RECORDS WITH SCHOOL/ACADEMY IN NAME BUT landmark_type='church' (sample) ===")
cur.execute("""
    SELECT name, denomination, faith, city, state, country
    FROM churches
    WHERE (name LIKE '%School%' OR name LIKE '%Academy%')
      AND landmark_type = 'church'
      AND name NOT LIKE '%Church%'
      AND name NOT LIKE '%Church %'
      AND name NOT LIKE '%Chapel%'
    ORDER BY RANDOM()
    LIMIT 30
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | {str(r['denomination'] or '')[:25]:25s} | {r['faith'] or '':15s} | {r['city'] or '':20s} {r['state'] or '':5s} {r['country'] or ''}")
print()

# Count them
cur.execute("""
    SELECT COUNT(*) as cnt
    FROM churches
    WHERE (name LIKE '%School%' OR name LIKE '%Academy%')
      AND landmark_type = 'church'
      AND name NOT LIKE '%Church%'
      AND name NOT LIKE '%Church %'
      AND name NOT LIKE '%Chapel%'
""")
cnt = cur.fetchone()[0]
print(f"  Count: {cnt}")
print()

# 7. Similar but with NULL landmark_type
print("=== RECORDS WITH SCHOOL/ACADEMY IN NAME AND NULL landmark_type (sample) ===")
cur.execute("""
    SELECT name, denomination, faith, city, state, country
    FROM churches
    WHERE (name LIKE '%School%' OR name LIKE '%Academy%')
      AND (landmark_type IS NULL OR landmark_type = '')
      AND name NOT LIKE '%Church%'
      AND name NOT LIKE '%Church %'
      AND name NOT LIKE '%Chapel%'
    ORDER BY RANDOM()
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | {str(r['denomination'] or '')[:25]:25s} | {r['faith'] or '':15s} | {r['city'] or '':20s} {r['state'] or '':5s} {r['country'] or ''}")
print()

cur.execute("""
    SELECT COUNT(*) as cnt
    FROM churches
    WHERE (name LIKE '%School%' OR name LIKE '%Academy%')
      AND (landmark_type IS NULL OR landmark_type = '')
      AND name NOT LIKE '%Church%'
      AND name NOT LIKE '%Church %'
      AND name NOT LIKE '%Chapel%'
""")
cnt = cur.fetchone()[0]
print(f"  Count: {cnt}")
print()

# 8. New metric: what about "name ends with School" or "name ends with Academy"?
print("=== RECORDS WHERE NAME ENDS WITH 'School' or 'Academy' (not 'Church School') ===")
cur.execute("""
    SELECT COUNT(*) as cnt FROM churches
    WHERE (name LIKE '% School' OR name LIKE '% Academy'
           OR name LIKE '% Schools' OR name LIKE '% Academies')
      AND landmark_type != 'school'
      AND name NOT LIKE '%Church School'
      AND name NOT LIKE '%Church % School'
""")
cnt = cur.fetchone()[0]
print(f"  Ending with School/Academy but not tagged as school: {cnt}")
print()

# 9. Check records ending with "School" or "Academy" (most likely pure schools)
print("=== SAMPLE: name ENDS with 'School' or 'Academy' - current landmark_type ===")
cur.execute("""
    SELECT name, landmark_type, faith, city, state, country
    FROM churches
    WHERE (name LIKE '% School' OR name LIKE '% Academy')
      AND landmark_type != 'school'
    ORDER BY RANDOM()
    LIMIT 25
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | lm={str(r['landmark_type'] or 'NULL'):15s} | {r['faith'] or '':12s} | {r['city'] or '':18s} {r['state'] or '':5s} {r['country'] or ''}")
print()

# 10. Check for Catholic-specific school patterns that are clearly schools
print("=== CATHOLIC SCHOOL PATTERNS (clearly schools, tagged wrong) ===")
cur.execute("""
    SELECT name, landmark_type, city, state, country
    FROM churches
    WHERE (name LIKE '%Catholic School%' OR name LIKE '%Catholic Academy%')
      AND landmark_type != 'school'
    ORDER BY RANDOM()
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | lm={str(r['landmark_type'] or 'NULL'):15s} | {r['city'] or '':18s} {r['state'] or '':5s} {r['country'] or ''}")
cnt = cur.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Catholic School%' OR name LIKE '%Catholic Academy%')
      AND landmark_type != 'school'
""").fetchone()[0]
print(f"  Count with wrong landmark: {cnt}")
print()

# 11. Check "University of" / "College of" / "Seminary of" patterns
print("=== SEMINARY RECORDS (likely mis-tagged) ===")
cur.execute("""
    SELECT COUNT(*) as cnt FROM churches
    WHERE (name LIKE '%Seminary%' OR name LIKE '%Yeshiva%')
      AND landmark_type != 'school'
""")
cnt = cur.fetchone()[0]
print(f"  Seminary/Yeshiva records not tagged as school: {cnt}")
cur.execute("""
    SELECT name, landmark_type, denomination, faith, city, state, country
    FROM churches
    WHERE (name LIKE '%Seminary%' OR name LIKE '%Yeshiva%')
      AND landmark_type != 'school'
    ORDER BY RANDOM()
    LIMIT 15
""")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | lm={str(r['landmark_type'] or 'NULL'):15s} | {str(r['denomination'] or '')[:20]} | {r['city'] or '':18s} {r['country'] or ''}")
print()

# 12. Look at records with lm='university' 
print("=== RECORDS WITH landmark_type='university' ===")
cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'university'")
print(f"  Count: {cur.fetchone()[0]}")
cur.execute("SELECT name, landmark_type, faith FROM churches WHERE landmark_type = 'university' LIMIT 10")
for r in cur.fetchall():
    print(f"  {r['name'][:55]:55s} | {r['faith'] or ''}")

db.close()

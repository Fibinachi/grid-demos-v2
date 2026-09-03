"""Detailed audit of school-related records in churches.db"""
import sqlite3
import json

db = sqlite3.connect("E:\\grid\\churches.db")
db.row_factory = sqlite3.Row
cur = db.cursor()

# 1. How many churches have school/education-related names?
school_keywords = [
    '%school%', '%academy%', '%college%', '%university%', '%seminary%',
    '%institute%', '%kindergarten%', '%preschool%', '%montessori%',
    '%education%', '%student%', '%learning%', '%high school%',
    '%elementary%', '%primary school%', '%secondary%', '%grammar school%',
    '%preparatory%', '%prep school%', '%nursery%', '%daycare%', '%child care%',
    '%campus%', '%boarding%', '%lyceum%', '%gymnasium%', '%yeshiva%',
    '%madrasa%', '%madrasah%', '%schoolhouse%', '%classroom%',
]

query = f"SELECT COUNT(*) FROM churches WHERE {' OR '.join(['name LIKE ?'] * len(school_keywords))}"
cur.execute(query, school_keywords)
total = cur.fetchone()[0]
print(f"=== CHURCHES WITH SCHOOL-RELATED NAMES: {total} ===")
print()

# 2. Also check landmark_type
cur.execute("SELECT DISTINCT landmark_type FROM churches WHERE landmark_type IS NOT NULL ORDER BY landmark_type")
ltypes = [r[0] for r in cur.fetchall()]
print("=== LANDMARK TYPES ===")
for lt in ltypes:
    cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = ?", (lt,))
    cnt = cur.fetchone()[0]
    print(f"  {lt:40s} {cnt}")
print()

# 3. Look for churches with school-related denominations
school_denoms = [
    '%school%', '%academy%', '%college%', '%university%', '%seminary%',
    '%institute%', '%education%', '%yeshiva%', '%madrasa%',
]
query2 = "SELECT COUNT(*) FROM churches WHERE " + " OR ".join(["denomination LIKE ?" for _ in school_denoms])
cur.execute(query2, school_denoms)
denom_cnt = cur.fetchone()[0]
print(f"=== CHURCHES WITH SCHOOL-RELATED DENOMINATIONS: {denom_cnt} ===")

# Show some examples
q_ex = "SELECT name, denomination, landmark_type, faith, city, state, country FROM churches WHERE " + " OR ".join(["denomination LIKE ?" for _ in school_denoms]) + " LIMIT 30"
cur.execute(q_ex, school_denoms)
rows = cur.fetchall()
for r in rows:
    print(f"  {r['name'][:50]:50s} | denom={str(r['denomination'])[:30]:30s} | lm={str(r['landmark_type'])[:15]:15s} | {r['faith'] or '':15s} | {r['city'] or '':20s} {r['state'] or '':5s} {r['country'] or ''}")
print()

# 4. Same for landmark_type
print("=== SCHOOL-RELATED LANDMARK TYPE COUNTS ===")
school_lm = [
    '%school%', '%academy%', '%college%', '%university%', '%seminary%',
    '%institute%', '%kindergarten%', '%preschool%', '%education%', '%campus%',
]
for slm in school_lm:
    cur.execute("SELECT COUNT(*) FROM churches WHERE landmark_type LIKE ?", (slm,))
    cnt = cur.fetchone()[0]
    if cnt > 0:
        print(f"  {slm:40s} {cnt}")
print()

# 5. Check pss_schools connection to churches
cur.execute("SELECT COUNT(*) FROM churches WHERE source = 'pss_schools'")
pss_churches = cur.fetchone()[0]
print(f"=== PSS SCHOOLS IN CHURCHES TABLE (source='pss_schools'): {pss_churches} ===")

# Check if pss_schools has a church_id
cur.execute("PRAGMA table_info(pss_schools)")
cols = [c[1] for c in cur.fetchall()]
print(f"  pss_schools columns: {cols}")

# 6. Sample qualifying records with school names
print()
print("=== SAMPLE: CHURCHES WITH 'UNIVERSITY' OR 'COLLEGE' IN NAME (NOT SEMINARY) ===")
cur.execute("""
    SELECT name, denomination, landmark_type, faith, faith_tradition, city, state, country
    FROM churches
    WHERE (name LIKE '%university%' OR name LIKE '%college%')
      AND name NOT LIKE '%seminary%'
      AND name NOT LIKE '%bible%'
      AND name NOT LIKE '%theological%'
    ORDER BY RANDOM()
    LIMIT 30
""")
rows = cur.fetchall()
for r in rows:
    print(f"  {r['name'][:55]:55s} | {str(r['denomination'] or '')[:25]:25s} | lm={str(r['landmark_type'] or '')[:18]:18s} | {str(r['faith'] or ''):12s} | {str(r['city'] or ''):18s} {str(r['state'] or ''):5s} {r['country'] or ''}")
print()

# 7. School-related denominations breakdown
print("=== SCHOOL DENOMINATION BREAKDOWN ===")
cur.execute("""
    SELECT denomination, COUNT(*) as cnt
    FROM churches
    WHERE (denomination LIKE '%school%' OR denomination LIKE '%academy%' OR denomination LIKE '%college%'
           OR denomination LIKE '%university%' OR denomination LIKE '%seminary%'
           OR denomination LIKE '%institute%' OR denomination LIKE '%education%')
      AND denomination NOT LIKE '%church%'
    GROUP BY denomination
    ORDER BY cnt DESC
    LIMIT 40
""")
rows = cur.fetchall()
for r in rows:
    print(f"  {r['denomination'][:50]:50s} {r['cnt']}")
print()

# 8. Check faith breakdown of school-name records
print("=== FAITH BREAKDOWN OF SCHOOL-NAME RECORDS ===")
cur.execute(f"""
    SELECT faith, COUNT(*) as cnt
    FROM churches
    WHERE {' OR '.join(['name LIKE ?'] * len(school_keywords))}
    GROUP BY faith
    ORDER BY cnt DESC
""", school_keywords)
rows = cur.fetchall()
for r in rows:
    print(f"  {str(r['faith'] or 'NULL'):20s} {r['cnt']}")
print()

# 9. Check for Catholic school patterns
print("=== CATHOLIC SCHOOL-RELATED (name patterns) ===")
catholic_school_patterns = [
    '%catholic school%', '%catholic academy%', '%st. % school%',
    '%st % school%', '%saint % school%', '%our lady%school%',
    '%sacre coeur%', '%sacred heart%school%',
]
for pat in catholic_school_patterns:
    cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND (faith = 'Christian' OR faith IS NULL)", (pat,))
    cnt = cur.fetchone()[0]
    if cnt > 0:
        print(f"  {pat:35s} {cnt}")

# Specifically check for "Catholic School" named entries
cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%catholic school%'")
cnt = cur.fetchone()[0]
print(f"\n  '%%catholic school%%' total: {cnt}")
cur.execute("SELECT name, denomination, landmark_type, city, state, country FROM churches WHERE name LIKE '%catholic school%' LIMIT 20")
for r in cur.fetchall():
    print(f"    {r['name'][:55]:55s} | {str(r['denomination'] or '')[:25]:25s} | lm={str(r['landmark_type'] or ''):15s} | {str(r['city'] or ''):18s} {str(r['state'] or ''):5s} {r['country'] or ''}")

# 10. Check for 'school' that might be proper church names with 'school' in denomination
print()
print("=== SCHOOL KEYWORD IN NAME BREAKDOWN BY LANDMARK_TYPE ===")
cur.execute(f"""
    SELECT landmark_type, COUNT(*) as cnt
    FROM churches
    WHERE name LIKE '%school%'
    GROUP BY landmark_type
    ORDER BY cnt DESC
""")
rows = cur.fetchall()
for r in rows:
    print(f"  {str(r['landmark_type'] or 'NULL'):25s} {r['cnt']}")

db.close()

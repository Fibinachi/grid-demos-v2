"""Investigate 'Mexican' denomination mislabeling"""
import sqlite3

db = sqlite3.connect(r"E:\grid\churches.db")
c = db.cursor()

# Distinct denomination values
q = "SELECT denomination, COUNT(*) as cnt FROM churches WHERE denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%' GROUP BY denomination ORDER BY cnt DESC"
c.execute(q)
print("=== Denomination values containing 'Mexican' ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:70]:70s}  {r[1]:>8,}")

# Country breakdown
q2 = "SELECT country, COUNT(*) as cnt FROM churches WHERE (denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%') AND country IS NOT NULL AND country != '' GROUP BY country ORDER BY cnt DESC"
c.execute(q2)
print("\n=== Country breakdown ===")
for r in c.fetchall():
    print(f"  {str(r[0]):15s}  {r[1]:>8,}")

# US vs MX vs other
q3 = """SELECT
    SUM(CASE WHEN country='US' THEN 1 ELSE 0 END) as in_us,
    SUM(CASE WHEN country='MX' THEN 1 ELSE 0 END) as in_mx,
    SUM(CASE WHEN country NOT IN ('US','MX') THEN 1 ELSE 0 END) as in_other
FROM churches
WHERE denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%'"""
c.execute(q3)
r = c.fetchone()
print(f"\n  US: {r[0]:>8,}  |  MX: {r[1]:>8,}  |  Other: {r[2]:>8,}")

# Sample some US records with Mexican denomination
q4 = "SELECT rowid, name, denomination, source, city, state FROM churches WHERE country='US' AND (denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%') LIMIT 20"
c.execute(q4)
print("\n=== Sample US records with 'Mexican' denomination ===")
for r in c.fetchall():
    print(f"  rowid={r[0]} name={str(r[1])[:55]:55s} denom={str(r[2])[:45]:45s} src={r[3]:25s} city={str(r[4])[:20]:20s} st={r[5]}")

# And check what the proper denomination values SHOULD be — 
# are these actually American Baptist, American churches etc. with a typo?
q5 = "SELECT rowid, name, denomination, source, city, state, faith FROM churches WHERE country='US' AND (denomination LIKE '%Mexican%' OR denomination LIKE '%mexican%') AND denomination NOT IN ('Mexican Baptist','Mexican Baptist Church') LIMIT 15"
c.execute(q5)
print("\n=== Non-Baptist Mexican denom in US ===")
for r in c.fetchall():
    print(f"  rowid={r[0]} name={str(r[1])[:55]:55s} denom={str(r[2])[:45]:45s} src={r[3]:20s} faith={r[6]:10s} city={str(r[4])[:20]} st={r[5]}")

# Check if some are "American" mislabeled as "Mexican"
q6 = "SELECT denomination, COUNT(*) FROM churches WHERE country='US' AND (denomination LIKE '%mexican%' OR denomination LIKE '%Mexican%') AND (denomination LIKE '%American%' OR denomination LIKE '%american%') GROUP BY denomination"
c.execute(q6)
print("\n=== 'American' + 'Mexican' combos ===")
for r in c.fetchall():
    print(f"  {str(r[0])[:70]:70s}  cnt={r[1]}")

db.close()

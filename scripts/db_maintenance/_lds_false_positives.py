"""Investigate false positives in LDS denomination data"""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()

# Check Saint John's in the Fields
c.execute("""
  SELECT id, name, denomination, faith, faith_tradition, 
         source, city, state, country
  FROM churches 
  WHERE name LIKE '%Saint John%Fields%'
""")
print("=== Saint John's in the Fields ===")
for r in c.fetchall():
    print(f"  ID={r[0]}: {r[1]}")
    print(f"  denom={r[2]!r} faith={r[3]!r} tradition={r[4]!r}")
    print(f"  source={r[5]!r} loc={r[6]}, {r[7]} {r[8]}")

# Check Fields of Harvest
c.execute("""
  SELECT id, name, denomination, faith, faith_tradition, 
         source, city, state, country
  FROM churches 
  WHERE name LIKE '%Fields of Harvest%' OR name LIKE '%Harvest Missions%'
""")
print("\n=== Fields of Harvest ===")
for r in c.fetchall():
    print(f"  ID={r[0]}: {r[1]}")
    print(f"  denom={r[2]!r} faith={r[3]!r} tradition={r[4]!r}")
    print(f"  source={r[5]!r} loc={r[6]}, {r[7]} {r[8]}")

# Find entries with LDS denomination but non-LDS names - check by source
print("\n=== Potential false positives: LDS denom + obviously non-LDS names ===")
c.execute("""
  SELECT name, denomination, source, country, COUNT(*) as cnt
  FROM churches
  WHERE (denomination LIKE '%Mormon/LDS%' OR denomination LIKE '%LDS / Mormon%' OR denomination LIKE '%LDS%')
  AND (
    name LIKE '%Catholic%' OR name LIKE '%Anglican%' OR name LIKE '%Baptist%'
    OR name LIKE '%Methodist%' OR name LIKE '%Lutheran%' OR name LIKE '%Presbyterian%'
    OR name LIKE '%Orthodox%' OR name LIKE '%Saint%Church%'
    OR name LIKE '%Episcopal%' OR name LIKE '%Pentecostal%'
    OR name LIKE '%Cathedral%' OR name LIKE '%Basilica%'
  )
  AND name NOT LIKE '%Latter%Day%' AND name NOT LIKE '%Latter%day%'
  AND name NOT LIKE '%Mormon%'
  GROUP BY name ORDER BY cnt DESC LIMIT 30
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0]} | src={r[2]} | {r[3]} x{r[4]}")

# Check: how many with LDS denom have obviously Christian non-LDS keywords?
print("\n=== Count of false positives by keyword ===")
keywords = ['Catholic', 'Anglican', 'Baptist', 'Methodist', 'Lutheran', 
            'Presbyterian', 'Orthodox', 'Episcopal', 'Pentecostal',
            'Cathedral', 'Basilica', 'Saint']
for kw in keywords:
    c.execute(f"""
      SELECT COUNT(*) FROM churches
      WHERE (denomination LIKE '%Mormon/LDS%' OR denomination LIKE '%LDS / Mormon%' OR denomination LIKE '%LDS%')
      AND name LIKE '%{kw}%'
      AND name NOT LIKE '%Latter%Day%' AND name NOT LIKE '%Mormon%'
    """)
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  {kw}: {cnt}")

# Check source breakdown for LDS denom
print("\n=== Source breakdown for LDS-denominated churches ===")
c.execute("""
  SELECT source, COUNT(*) FROM churches
  WHERE (denomination LIKE '%Mormon/LDS%' OR denomination LIKE '%LDS / Mormon%')
  GROUP BY source ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

# Look at the specific source that gave us Saint John's
c.execute("""
  SELECT source, COUNT(*) FROM churches
  WHERE name LIKE '%Saint John%Fields%'
""")
print("\nSource for Saint John's:")
for r in c.fetchall():
    print(f"  {r[0]!r}")

db.close()

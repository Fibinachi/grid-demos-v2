"""Explore LDS/Mormon data in churches.db"""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()

# Count LDS entries
c.execute("""SELECT COUNT(*) FROM churches WHERE faith = 'Christian' 
  AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%' 
       OR denomination LIKE '%Reorganized%' OR denomination LIKE '%RLDS%' 
       OR denomination LIKE '%Community of Christ%' 
       OR name LIKE '%Latter%Day%' OR name LIKE '%Mormon%' 
       OR name LIKE '%Ward%' OR name LIKE '%Stake%')""")
print(f"LDS-like entries: {c.fetchone()[0]}")

# What denominations exist?
c.execute("""SELECT denomination, COUNT(*) FROM churches 
  WHERE faith='Christian' AND (
    denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%' 
    OR denomination LIKE '%Reorganized%' OR denomination LIKE '%RLDS%' 
    OR denomination LIKE '%Community of Christ%')
  GROUP BY denomination ORDER BY COUNT(*) DESC""")
print('\n=== Denominations ===')
for row in c.fetchall():
    print(f'  [{row[0]}]: {row[1]}')

# What name patterns exist (top 50)?
c.execute("""SELECT name, COUNT(*) FROM churches 
  WHERE (name LIKE '%Ward%' OR name LIKE '%Stake%' OR name LIKE '%Latter%Day%' 
         OR name LIKE '%Mormon%') AND faith='Christian' 
  GROUP BY name ORDER BY COUNT(*) DESC LIMIT 50""")
print('\n=== Name patterns (top 50) ===')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Count by type keywords in name
c.execute("""SELECT 
  SUM(CASE WHEN name LIKE '%Stake Center%' OR name LIKE '%Stake Centre%' THEN 1 ELSE 0 END) as stake_centers,
  SUM(CASE WHEN name LIKE '%Stake%' AND name NOT LIKE '%Stake Center%' AND name NOT LIKE '%Stake Centre%' THEN 1 ELSE 0 END) as stake_other,
  SUM(CASE WHEN name LIKE '%Ward%' THEN 1 ELSE 0 END) as wards,
  SUM(CASE WHEN name LIKE '%Branch%' AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%') THEN 1 ELSE 0 END) as branches,
  SUM(CASE WHEN name LIKE '%Meetinghouse%' OR name LIKE '%Meeting house%' THEN 1 ELSE 0 END) as meetinghouses,
  SUM(CASE WHEN name LIKE '%Institute%' THEN 1 ELSE 0 END) as institutes,
  SUM(CASE WHEN name LIKE '%Temple%' AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%') THEN 1 ELSE 0 END) as temples
FROM churches WHERE faith='Christian' AND (
  denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%' 
  OR name LIKE '%Ward%' OR name LIKE '%Stake%' 
  OR name LIKE '%Latter%Day%' OR name LIKE '%Mormon%')""")
row = c.fetchone()
print('\n=== Type counts ===')
for k, v in zip(['stake_centers','stake_other','wards','branches','meetinghouses','institutes','temples'], row):
    print(f'  {k}: {v}')

# Look at name patterns with Stake
c.execute("""SELECT name, COUNT(*) FROM churches 
  WHERE name LIKE '%Stake%' AND faith='Christian'
  GROUP BY name ORDER BY COUNT(*) DESC LIMIT 30""")
print('\n=== Stake entries (top 30) ===')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Look at name patterns with Ward 
c.execute("""SELECT name, COUNT(*) FROM churches 
  WHERE name LIKE '%Ward%' AND faith='Christian'
  GROUP BY name ORDER BY COUNT(*) DESC LIMIT 30""")
print('\n=== Ward entries (top 30) ===')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Country breakdown
c.execute("""SELECT country, COUNT(*) FROM churches 
  WHERE denomination LIKE '%Latter%Day Saint%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%'
  GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20""")
print('\n=== Country breakdown (LDS denom) ===')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

# Temples
c.execute("""SELECT id, name, city, state, country, latitude, longitude FROM churches 
  WHERE name LIKE '%Temple%' AND (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  ORDER BY country, state, city""")
temples = c.fetchall()
print(f'\n=== Temples ({len(temples)}) ===')
for t in temples:
    print(f'  {t[1]} | {t[2]}, {t[3] if t[3] else ""} {t[4]}')

# Check faith_tradition for LDS
c.execute("""SELECT faith_tradition, COUNT(*) FROM churches 
  WHERE denomination LIKE '%Latter%Day Saint%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%'
  GROUP BY faith_tradition""")
print('\n=== Faith tradition breakdown ===')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]}')

db.close()

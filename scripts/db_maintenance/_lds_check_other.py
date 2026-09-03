"""Check what the LDS filter is catching - diagnose false positives"""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()

# What denominations match our LDS filter?
c.execute("""
  SELECT denomination, COUNT(*) FROM churches
  WHERE (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  AND latitude IS NOT NULL
  GROUP BY denomination ORDER BY COUNT(*) DESC
""")
print('Denominations matching LDS filter:')
for r in c.fetchall():
    print(f'  [{r[0]}]: {r[1]}')

# Check specific case user mentioned
c.execute("SELECT id, name, denomination, city, state, country FROM churches WHERE name LIKE '%Saint John%Fields%'")
print('\nSaint John in Fields:')
for r in c.fetchall():
    print(f'  ID={r[0]}: {r[1]} | denom=[{r[2]}] | {r[3]}, {r[4]} {r[5]}')

# What denomination does it actually have?
c.execute("SELECT id, name, denomination, faith, faith_tradition FROM churches WHERE name LIKE '%Saint John%Fields%'")
print('\nSaint John in Fields - full faith info:')
for r in c.fetchall():
    print(f'  ID={r[0]}: denom=[{r[2]}] faith=[{r[3]}] tradition=[{r[4]}]')

# Check if %LDS% is the problem
c.execute("""
  SELECT denomination, COUNT(*) FROM churches
  WHERE denomination LIKE '%LDS%' 
  AND denomination NOT LIKE '%Latter%Day%' 
  AND denomination NOT LIKE '%Mormon%'
  AND latitude IS NOT NULL
  GROUP BY denomination ORDER BY COUNT(*) DESC
""")
print('\nDenominations matching %LDS% but NOT Latter-Day or Mormon:')
for r in c.fetchall():
    print(f'  [{r[0]}]: {r[1]}')

# Check broader: what denominations have LDS in them?
c.execute("""
  SELECT DISTINCT denomination FROM churches
  WHERE denomination LIKE '%LDS%'
  ORDER BY denomination
""")
print('\nAll denominations containing "LDS":')
for r in c.fetchall():
    print(f'  [{r[0]}]')

# What about the other LDS entries - sample names
c.execute("""
  SELECT name, denomination, country, COUNT(*) FROM churches
  WHERE (denomination LIKE '%Latter%Day%' OR denomination LIKE '%LDS%' OR denomination LIKE '%Mormon%')
  AND latitude IS NOT NULL
  AND name NOT LIKE '%Temple%'
  AND name NOT LIKE '%Stake%' AND name NOT LIKE '%Ward%'
  AND name NOT LIKE '%Branch%' AND name NOT LIKE '%Meeting%'
  AND name NOT LIKE '%Institute%' AND name NOT LIKE '%Seminary%'
  AND name NOT LIKE '%Mission%'
  GROUP BY name ORDER BY COUNT(*) DESC LIMIT 40
""")
print('\nTop unclassified LDS names:')
for r in c.fetchall():
    print(f'  [{r[1]}] {r[0]} ({r[2]}) x{r[3]}')

db.close()

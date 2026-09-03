"""Deep analysis of Salvation Army name patterns for hierarchy design."""
import sqlite3, re

db = sqlite3.connect('E:\\grid\\churches.db')

# All names that aren't just "Salvation Army"
print("=== Names with corp/citadel/temple/detail ===")
cur = db.execute("""
  SELECT name, city, state, country, COUNT(*) as cnt
  FROM churches
  WHERE name LIKE '%Salvation Army%' AND name NOT IN ('Salvation Army', 'SALVATION ARMY', 'salvation army', 'Salvation army', 'salvation army church', 'salvation army church')
    AND LENGTH(name) > 25
  GROUP BY name, city, state, country
  ORDER BY cnt DESC
  LIMIT 80
""")
for r in cur:
    print(f'  {r[4]:>3} | {r[0]:70s} | {str(r[1] or ""):25s} | {str(r[2] or ""):15s} | {str(r[3] or "")}')

# Look for specific keywords
print("\n=== Keyword analysis ===")
for kw in ['Corps', 'Citadel', 'Temple', 'HQ', 'Headquarters', 'Territorial', 'Divisional',
           'Community', 'Thrift', 'Social', 'Shelter', 'Centre', 'Center', 
           'Chapel', 'Hall', 'Church', 'Outpost', 'School', 'Hospital',
           'Employment', 'Family', 'Youth', 'Senior', 'Convalescent',
           'Home', 'Lodge', 'Hostel', 'Retirement', 'Nursing']:
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ?", (f'%{kw}%',))
    c = cur.fetchone()[0]
    if c > 0:
        cur2 = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%')", (f'%{kw}%',))
        c2 = cur2.fetchone()[0]
        print(f'  {kw:20s} | total: {c:>5} | SA: {c2:>5}')

# Corps extraction - patterns like "X Corps", "X Corps Church", "X Temple Corps"
print("\n=== Corps-level entries ===")
cur = db.execute("""
  SELECT name, city, state, country, COUNT(*) as cnt
  FROM churches
  WHERE name LIKE '%Corps%' AND (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%')
  GROUP BY name, city, state, country
  ORDER BY cnt DESC
  LIMIT 100
""")
for r in cur:
    print(f'  {r[4]:>3} | {r[0]:75s} | {str(r[1] or ""):25s} | {str(r[2] or ""):15s} | {r[3]}')

# "The Salvation Army" vs just "Salvation Army"
print("\n=== 'The Salvation Army' vs 'Salvation Army' ===")
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE 'The Salvation Army%'")
print(f"  'The Salvation Army%': {cur.fetchone()[0]}")
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE 'Salvation Army%' AND name NOT LIKE 'The Salvation Army%'")
print(f"  'Salvation Army%' (not The): {cur.fetchone()[0]}")

# Check for non-English names
print("\n=== Non-English names (containing non-ASCII) ===")
cur = db.execute("""
  SELECT name, city, country, COUNT(*) as cnt
  FROM churches
  WHERE (name LIKE '%Salvation Army%' OR name LIKE '%Armée du Salut%' OR name LIKE '%Ejército de Salvación%' 
         OR name LIKE '%Heilsarmee%' OR name LIKE '%L'Armée du Salut%' OR name LIKE '%Frelsesarmeen%'
         OR name LIKE '%Frälsningsarmén%' OR name LIKE '%Salvasjon%')
    AND name GLOB '*[^a-zA-Z0-9 &''.,/-]*'
  GROUP BY name, city, country
  ORDER BY cnt DESC
  LIMIT 30
""")
for r in cur:
    print(f'  {r[3]:>3} | {r[0]:70s} | {str(r[1] or ""):25s} | {r[2]}')

# French/Canadian names
print("\n=== French names ===")
cur = db.execute("""
  SELECT name, city, country, COUNT(*) as cnt
  FROM churches
  WHERE (name LIKE '%Armée du Salut%' OR name LIKE '%Armée%Salut%')
  GROUP BY name, city, country
  ORDER BY cnt DESC
  LIMIT 20
""")
for r in cur:
    print(f'  {r[3]:>3} | {r[0]:70s} | {str(r[1] or ""):25s} | {r[2]}')

# Check GOVERNING COUNCIL entries
print("\n=== Governing Council entries ===")
cur = db.execute("""
  SELECT name, city, state, country
  FROM churches
  WHERE name LIKE '%GOVERNING COUNCIL%'
  LIMIT 30
""")
for r in cur:
    print(f'  {r[0]:80s} | {str(r[1] or ""):25s} | {str(r[2] or ""):15s} | {r[3]}')

db.close()

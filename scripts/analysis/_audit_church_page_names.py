"""Audit: find church names that look like page/article artifacts."""
from gw_db import connect

db = connect()
c = db.cursor()

# 1. Names ending in .HTML (scraped article titles stored as church names)
c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%.html%' OR name LIKE '%.HTM%'")
print(f"Names with .html/.htm: {c.fetchone()[0]}")

# 2. Names containing http or www
c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%http%' OR name LIKE '%www.%'")
print(f"Names with http/www: {c.fetchone()[0]}")

# 3. Show all .html names in detail
print()
print("=== ALL names ending with .html (or .HTM) ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%.html' OR name LIKE '%.HTM'
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
total = 0
print(f"Total unique .html patterns: {len(rows)}")
for r in rows:
    total += r[1]
    print(f"  [{r[1]}] {r[0][:150]}")
print(f"Grand total records with .html names: {total}")

# 4. What sources do .html names come from?
print()
print("=== Sources of .html names ===")
c.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%.html' OR name LIKE '%.HTM'
    GROUP BY source
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

# 5. Names with URLs
print()
print("=== Names with URLs (http/www/goo.gl) ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%http%' OR name LIKE '%www.%' OR name LIKE '%goo.gl%'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 30
""")
rows = c.fetchall()
for r in rows:
    print(f"  [{r[2]}] source={r[1]!r} {r[0][:120]}")

# 6. Names with social page patterns
print()
print("=== 'GROUP PAGE', 'PUBLIC PAGE', 'MEMORIAL PAGE' ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%GROUP PAGE%' OR name LIKE '%PUBLIC PAGE%' 
       OR name LIKE '%MEMORIAL PAGE%'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 30
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0][:100]}")

# 7. Check for other article-like patterns (news headlines, etc.)
print()
print("=== Names that look like news/article titles (start with common patterns) ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE (name LIKE 'SAINT % TO %' OR name LIKE 'SAINT % AND %' 
           OR name LIKE 'CHURCH % TO %' OR name LIKE 'US CATHOLIC%')
    AND LENGTH(name) > 60
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 30
""")
rows = c.fetchall()
print(f"Found {len(rows)} long article-like names:")
for r in rows:
    print(f"  [{r[2]}] source={r[1]!r} {r[0][:120]}")

# 8. Check if "CANADA - FRENCH" or "CANADA / FRENCH" type names exist
print()
print("=== 'CANADA /' or 'CANADA -' in names ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE 'CANADA /%' OR name LIKE 'CANADA -%'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 10
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0][:100]}")

# 9. Names that look like Facebook event/fundraiser pages
print()
print("=== Names with 'FUNDRAISER' or 'EVENT' or 'DONATION' ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%FUNDRAISER%' OR name LIKE '% DONATION%' 
       OR name LIKE '% EVENT%' OR name LIKE '%CAMPAIGN%'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0][:100]}")

# 10. Names starting with numbers (likely IDs, not real names)
print()
print("=== Names starting with a digit (IDs, ticket numbers?) ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE name GLOB '[0-9]*'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0][:80]}")

print()
print("Done.")

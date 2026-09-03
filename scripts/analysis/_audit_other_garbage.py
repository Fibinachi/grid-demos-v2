"""Check non-catholic_diocese_scrape garbage records."""
from gw_db import connect

db = connect()
c = db.cursor()

# 1. Names that are just URLs - what sources?
print("=== Names that are URLs (any source) ===")
c.execute("""
    SELECT source, COUNT(*) FROM churches
    WHERE (name LIKE 'http%' OR name LIKE 'www.%' OR name LIKE 'Https:%' OR name LIKE '%goo.gl/maps%')
       AND (name NOT LIKE '% %' OR name = name)  -- all of them
    GROUP BY source ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

# Show all URL-only names (no actual descriptive text)
print()
c.execute("""
    SELECT name, source, COUNT(*) FROM churches
    WHERE (name LIKE 'http%' OR name LIKE 'www.%' OR name LIKE 'Https:%' OR name LIKE '%goo.gl/maps%')
       AND name NOT LIKE '% - %' AND name NOT LIKE '% @%'
       AND LENGTH(name) < 100
    GROUP BY name ORDER BY COUNT(*) DESC
""")
rows = c.fetchall()
for r in rows:
    print(f"  [{r[2]}] src={r[1]!r} {r[0][:100]}")

# 2. Social pages by source
print()
print("=== Social pages (PUBLIC/GROUP/MEMORIAL PAGE) by source ===")
c.execute("""
    SELECT source, COUNT(*) FROM churches
    WHERE (name LIKE '%PUBLIC PAGE%' OR name LIKE '%GROUP PAGE%' OR name LIKE '%MEMORIAL PAGE%')
    GROUP BY source ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  {r[0]!r}: {r[1]}")

# 3. Names starting with "www." (likely URLs with website suffix but no category)
print()
print("=== Names starting with 'www.' ===")
c.execute("""
    SELECT name, source, COUNT(*) FROM churches
    WHERE name LIKE 'www.%'
    GROUP BY name ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f"  [{r[2]}] src={r[1]!r} {r[0][:80]}")

# 4. ANY name from overture_full that looks like a job posting
print()
print("=== Job-like names from any source ===")
c.execute("""
    SELECT name, source, COUNT(*) FROM churches
    WHERE (name LIKE '%TECHNICIAN%' OR name LIKE '%MAINTENANCE%' OR name LIKE '%DIRECTOR OF%'
           OR name LIKE '%COORDINATOR%' OR name LIKE '%ASSISTANT%' OR name LIKE '%MANAGER%')
    AND name NOT LIKE '%CHURCH%' AND name NOT LIKE '%CENTER%' AND LENGTH(name) < 80
    GROUP BY name ORDER BY COUNT(*) DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  [{r[2]}] src={r[1]!r} {r[0][:80]}")

db.close()

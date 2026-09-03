"""Audit: comprehensive look at page-name artifacts in church names."""
from gw_db import connect

db = connect()
c = db.cursor()

# 1. ALL names from catholic_diocese_scrape — this source seems dirty
print("=== ALL names from catholic_diocese_scrape source ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE source = 'catholic_diocese_scrape'
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"Total unique names: {len(rows)}")
total_records = sum(r[1] for r in rows)
print(f"Total records: {total_records}")
print()
for r in rows:
    print(f"  [{r[1]}] {r[0][:150]}")
    if r[1] > 1:
        print(f"         (appears {r[1]} times)")

# 2. Count names with ".html" (with or without extension cleanup needed)
print()
print("=== .html names + their potential clean versions ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%.html' OR name LIKE '%.HTM'
    GROUP BY name 
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    clean = r[0].rsplit('.', 1)[0]  # Remove .html/.HTM
    still_has = c.execute("SELECT COUNT(*) FROM churches WHERE name = ?", (clean,)).fetchone()[0]
    print(f"  [{r[1]}] {r[0][:100]}")
    print(f"         Clean version: {clean[:100]}")
    if still_has > 0:
        print(f"         ⚠ Also exists (already): {still_has} records")
    print()

# 3. Names that are just URLs (no real name at all)
print()
print("=== Names that are essentially just URLs ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE (name LIKE 'http%' OR name LIKE 'www.%' OR name LIKE 'Https:%' 
           OR name LIKE '%goo.gl/maps%')
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
for r in rows:
    print(f"  [{r[2]}] source={r[1]!r} {r[0][:120]}")

# 4. Social/Group/Memorial page names
print()
print("=== Social page names (PUBLIC PAGE, GROUP PAGE, MEMORIAL PAGE) ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE name LIKE '%PUBLIC PAGE%' OR name LIKE '%GROUP PAGE%' OR name LIKE '%MEMORIAL PAGE%'
    GROUP BY name 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
for r in rows:
    print(f"  [{r[2]}] source={r[1]!r} {r[0][:120]}")

# 5. Article-like names from catholic_diocese_scrape that DON'T have .html
print()
print("=== Article-like names (no .html) from catholic_diocese_scrape ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE source = 'catholic_diocese_scrape' 
    AND name NOT LIKE '%.html' AND name NOT LIKE '%.HTM'
    AND name NOT LIKE '%CATHEDRAL%' AND name NOT LIKE '%CHURCH%'
    AND name NOT LIKE '%PARISH%' AND name NOT LIKE '%CATHOLIC%'
    AND LENGTH(name) > 40
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"Found {len(rows)}:")
for r in rows:
    print(f"  [{r[1]}] {r[0][:150]}")

# 6. Check what other sources have news-like names
print()
print("=== Other sources with article-like names ===")
c.execute("""
    SELECT name, source, COUNT(*) as cnt 
    FROM churches 
    WHERE source IN ('overture_full', 'holy_sites_import', 'osm_import')
    AND name LIKE 'SAINT % TO %'
    AND name NOT LIKE '%CHURCH%' AND name NOT LIKE '%PARISH%'
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in c.fetchall():
    print(f"  [{r[2]}] source={r[1]!r} {r[0][:120]}")

print()
print("Done.")

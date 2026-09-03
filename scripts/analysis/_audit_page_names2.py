"""Deeper audit: find all denomination values with '/' and identify page-name artifacts."""
from gw_db import connect

db = connect()
c = db.cursor()

# All denomination values with '/'
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%/%'
    GROUP BY denomination 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"All {len(rows)} denomination values with '/':")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Check for short page-name-like patterns (e.g., "Page X", "Article", "Chapter")
print("\n=== denomination containing 'Page ', 'Article ', 'Chapter ' ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%Page %' OR denomination LIKE '%Article %'
       OR denomination LIKE '%Chapter %' OR denomination LIKE '%Section %'
    GROUP BY denomination 
    ORDER BY cnt DESC
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Check denomination values longer than 80 chars (likely scraped text, not real denomination)
print("\n=== denomination > 80 chars ===")
c.execute("""
    SELECT denomination, LENGTH(denomination) as l, COUNT(*) as cnt 
    FROM churches 
    WHERE LENGTH(denomination) > 80
    GROUP BY denomination 
    ORDER BY cnt DESC
    LIMIT 30
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  [{r[1]} chars] {r[0]!r}: {r[2]}")

# Check denomination with pipe characters
print("\n=== denomination with '|' ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%|%'
    GROUP BY denomination 
    ORDER BY cnt DESC
    LIMIT 20
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Check denomination with newlines or tabs
print("\n=== denomination with newline/tab ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%\n%' OR denomination LIKE '%\r%' OR denomination LIKE '%\t%'
    GROUP BY denomination 
    ORDER BY cnt DESC
    LIMIT 20
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Check source field values broadly
print("\n=== All unique source values ===")
c.execute("SELECT DISTINCT source FROM churches ORDER BY source")
rows = c.fetchall()
print(f"Found {len(rows)} source values:")
for r in rows:
    print(f"  {r[0]!r}")

# Check church_contacts table for page-like association names
print("\n=== church_contacts fields with page-like values ===")
for col in ['denomination_name', 'group_name', 'association_name']:
    try:
        c.execute(f"SELECT DISTINCT {col} FROM church_contacts WHERE {col} IS NOT NULL AND ({col} LIKE '%/%' OR {col} LIKE '%http%' OR LENGTH({col}) > 100) LIMIT 20")
        rows = c.fetchall()
        if rows:
            print(f"  {col}:")
            for r in rows:
                print(f"    {r[0]!r}")
        else:
            print(f"  {col}: (no issues)")
    except Exception as e:
        print(f"  {col}: ERROR - {e}")

# Check for double-brackets or wiki-style markup in any text field
print("\n=== denomination with wiki markup '{{' or '[[' ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '{{%' OR denomination LIKE '[[%'
    GROUP BY denomination 
    ORDER BY cnt DESC
    LIMIT 20
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

print("\nDone.")

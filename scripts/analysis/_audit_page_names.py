"""Audit: find denomination/association values that look like page names or URLs."""
from gw_db import connect

db = connect()
c = db.cursor()

# Pattern 1: Contains slashes (URL-like paths)
print("=== Contains '/' (URL/page path-like) ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%/%' OR denomination LIKE '%\\%'
    GROUP BY denomination 
    ORDER BY cnt DESC 
    LIMIT 50
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 2: Contains .html, .htm, .php, .asp
print("\n=== Contains file extensions (.html/.htm/.php/.asp) ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%.html%' OR denomination LIKE '%.htm%' 
       OR denomination LIKE '%.php%' OR denomination LIKE '%.asp%'
    GROUP BY denomination 
    ORDER BY cnt DESC 
    LIMIT 50
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 3: Contains http/https/www
print("\n=== Contains http/https/www ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%http%' OR denomination LIKE '%www.%'
    GROUP BY denomination 
    ORDER BY cnt DESC 
    LIMIT 50
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 4: Contains 'wiki' or 'Wikipedia' or 'page'
print("\n=== Contains 'wiki' or 'page' ===")
c.execute("""
    SELECT denomination, COUNT(*) as cnt 
    FROM churches 
    WHERE denomination LIKE '%wiki%' OR denomination LIKE '%page%'
       OR denomination LIKE '%Wikipedia%'
    GROUP BY denomination 
    ORDER BY cnt DESC 
    LIMIT 50
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 5: Look at the faith_tradition field for similar issues
print("\n=== faith_tradition values with '/' ===")
c.execute("""
    SELECT faith_tradition, COUNT(*) as cnt 
    FROM churches 
    WHERE faith_tradition LIKE '%/%' OR faith_tradition LIKE '%http%'
    GROUP BY faith_tradition 
    ORDER BY cnt DESC 
    LIMIT 30
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 6: Check church_enrichment association fields
print("\n=== church_enrichment.association with page-like names ===")
c.execute("""
    SELECT association, COUNT(*) as cnt 
    FROM church_enrichment 
    WHERE association LIKE '%/%' OR association LIKE '%http%' 
       OR association LIKE '%www.%' OR association LIKE '%.html%'
    GROUP BY association 
    ORDER BY cnt DESC 
    LIMIT 50
""")
rows = c.fetchall()
print(f"Found {len(rows)} values:")
for r in rows:
    print(f"  {r[0]!r}: {r[1]}")

# Pattern 7: IRS category/code fields with page-like names
print("\n=== Checking other text fields for page names ===")
for tbl, col in [('churches', 'source'), ('churches', 'denomination'), ('church_enrichment', 'association')]:
    c.execute(f"""
        SELECT COUNT(*) FROM {tbl} 
        WHERE {col} LIKE '%/%' OR {col} LIKE '%http%' 
           OR {col} LIKE '%www.%' OR {col} LIKE '%.html%'
    """)
    cnt = c.fetchone()[0]
    print(f"  {tbl}.{col}: {cnt} records with page-like names")

print("\nDone.")

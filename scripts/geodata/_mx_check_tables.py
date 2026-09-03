"""Quick check of census tract infrastructure and Mexico tables."""
from gw_db import connect

conn = connect()

# tract_lookup_us schema
cur = conn.execute("PRAGMA table_info(tract_lookup_us)")
cols = cur.fetchall()
print("tract_lookup_us columns:")
for c in cols:
    print(f"  {c[1]:30s} {c[2]:20s}")

cur = conn.execute("SELECT * FROM tract_lookup_us LIMIT 3")
print("\nSample rows:")
for r in cur.fetchall():
    print(r)

# Search for Mexico-related tables
cur = conn.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table'
    AND (name LIKE '%mx%' OR name LIKE '%mex%' OR name LIKE '%ageb%'
         OR name LIKE '%inegi%' OR name LIKE '%mexico%')
    ORDER BY name
""")
print("\nMexico-related tables:")
for t in cur.fetchall():
    print(f"  {t[0]}")

# Check county_fips_lookup - might have Mexico entries?
cur = conn.execute("PRAGMA table_info(county_fips_lookup)")
cols = cur.fetchall()
print("\ncounty_fips_lookup columns:")
for c in cols:
    print(f"  {c[1]:30s} {c[2]:20s}")

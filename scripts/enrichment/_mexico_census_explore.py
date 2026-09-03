"""Explore Mexican data before building census tract matching."""
from gw_db import connect

conn = connect()

# 1. All tables
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cur.fetchall()]
print(f"Total tables: {len(tables)}")
print("All tables:", tables)

# 2. Mexican churches - count and sample
cur = conn.execute("SELECT COUNT(*) FROM churches WHERE country = 'MX'")
print(f"\nMexican churches: {cur.fetchone()[0]}")

# 3. Sample Mexican churches with GPS
cur = conn.execute("""
    SELECT id, name, city, state, latitude, longitude, geocode_source
    FROM churches
    WHERE country = 'MX' AND latitude IS NOT NULL
    LIMIT 10
""")
rows = cur.fetchall()
print(f"\nSample Mexican churches with GPS ({len(rows)}):")
for r in rows:
    print(f"  {r[0]:8d} | {str(r[1]):50s} | {str(r[2]):20s} | {str(r[3]):20s} | {r[4]:9.5f} | {r[5]:9.5f} | {r[6]}")

# 4. GPS coverage
cur = conn.execute("""
    SELECT geocode_source, COUNT(*) as cnt
    FROM churches WHERE country = 'MX'
    GROUP BY geocode_source
    ORDER BY cnt DESC
""")
print("\nGPS coverage by source:")
for r in cur.fetchall():
    print(f"  {r[0]:20s} {r[1]:8d}")

cur = conn.execute("""
    SELECT COUNT(*) FROM churches
    WHERE country = 'MX' AND latitude IS NOT NULL
""")
with_gps = cur.fetchone()[0]
cur = conn.execute("SELECT COUNT(*) FROM churches WHERE country = 'MX'")
total = cur.fetchone()[0]
print(f"\nGPS coverage: {with_gps}/{total} ({with_gps/total*100:.1f}%)")

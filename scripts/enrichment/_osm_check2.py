import sqlite3
db = sqlite3.connect('E:/grid/churches.db')

# holy_sites columns
print("--- holy_sites columns ---")
for r in db.execute("PRAGMA table_info(holy_sites)"):
    print(f"  {r[1]}: {r[2]}")

# Co-location check
print("\n--- Spatial overlap ---")
overlap = db.execute("""
    SELECT COUNT(*) FROM (
        SELECT DISTINCT h.id FROM holy_sites h
        INNER JOIN churches c ON ABS(c.latitude - h.lat) < 0.001 
                             AND ABS(c.longitude - h.lon) < 0.001
        WHERE c.latitude IS NOT NULL AND h.lat IS NOT NULL
    )
""").fetchone()[0]
print(f"holy_sites co-located with churches (~100m): {overlap:,}")

# How many holy_sites have no matching church
total_hs = db.execute("SELECT COUNT(*) FROM holy_sites WHERE lat IS NOT NULL").fetchone()[0]
print(f"\nholy_sites geocoded: {total_hs:,}")
print(f"holy_sites with no church match: {total_hs - overlap:,}")
db.close()

"""Audit null-faith entries to understand the remaining pool."""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")

print("=== Null faith by country (top 20) ===")
rows = db.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches
    WHERE faith IS NULL OR faith = ''
    GROUP BY country
    ORDER BY cnt DESC
    LIMIT 20
""").fetchall()
for r in rows:
    print(f"  {r[0]:5s} {r[1]:>10,}")

print("\n=== Null faith by source (top 10) ===")
rows = db.execute("""
    SELECT source, COUNT(*) as cnt
    FROM churches
    WHERE faith IS NULL OR faith = ''
    GROUP BY source
    ORDER BY cnt DESC
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {r[0]:30s} {r[1]:>10,}")

print("\n=== Sample null-faith entries ===")
rows = db.execute("""
    SELECT name, country, landmark_type, source
    FROM churches
    WHERE (faith IS NULL OR faith = '') AND name IS NOT NULL
    LIMIT 30
""").fetchall()
for r in rows:
    print(f"  {str(r[0]):50s}  {str(r[1]):5s}  {str(r[2]):20s}  {str(r[3]):25s}")

print("\n=== Null-faith entries with Chinese characters ===")
rows = db.execute("""
    SELECT name, country
    FROM churches
    WHERE (faith IS NULL OR faith = '')
    AND (name LIKE '%寺%' OR name LIKE '%廟%' OR name LIKE '%宮%' OR name LIKE '%祠%' OR name LIKE '%教會%' OR name LIKE '%教堂%')
    LIMIT 20
""").fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  {str(r[0]):50s}  {r[1]:5s}")

print("\n=== Null-faith entries in JP with shrine patterns ===")
rows = db.execute("""
    SELECT name, landmark_type
    FROM churches
    WHERE (faith IS NULL OR faith = '') AND country = 'JP'
    LIMIT 20
""").fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  {str(r[0]):50s}  {r[1]:20s}")

db.close()

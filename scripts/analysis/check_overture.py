import sqlite3
db = sqlite3.connect('churches.db')
cur = db.cursor()

# Check Overture records in DB - what categories are there?
rows = cur.execute("SELECT source, COUNT(*) FROM churches WHERE source LIKE '%overture%' GROUP BY source").fetchall()
print("Overture sources in DB:")
for r in rows:
    print(f'  {r[0]}: {r[1]}')

print()

# Check what Overture categories we have
rows = cur.execute("SELECT overture_category, COUNT(*) as cnt FROM churches WHERE overture_category IS NOT NULL GROUP BY overture_category ORDER BY cnt DESC").fetchall()
print("Overture categories:")
for r in rows:
    cat = r[0] if r[0] else "(null)"
    print(f'  {cat:45s}: {r[1]}')

print()

# Check Overture brand data
rows = cur.execute("SELECT overture_brand, COUNT(*) as cnt FROM churches WHERE overture_brand IS NOT NULL GROUP BY overture_brand ORDER BY cnt DESC LIMIT 20").fetchall()
print("Overture brands:")
for r in rows:
    brand = r[0] if r[0] else "(null)"
    print(f'  {brand:45s}: {r[1]}')

# Check for Kingdom Hall in overture data
rows = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%' AND (name LIKE '%Kingdom Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Witness%')").fetchone()[0]
print(f"\nOverture records matching JW patterns: {rows}")

# Check total overture records
total = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%'").fetchone()[0]
print(f"Total Overture records in DB: {total}")

db.close()

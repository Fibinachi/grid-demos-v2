import sqlite3
db = sqlite3.connect('churches.db')
cur = db.cursor()

# Quick schema
cols = cur.execute("PRAGMA table_info(churches)").fetchall()
for c in cols:
    print(f"{c[1]}|{c[2]}")
print()

# Overture count
r = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%'").fetchone()[0]
print(f"Total overture records: {r}")

# JW in overture
r = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%' AND (name LIKE '%Kingdom%' OR name LIKE '%Jehovah%' OR name LIKE '%Witness%')").fetchone()[0]
print(f"JW-like in overture: {r}")

# JW in ALL data - how many total with kingdom/jehovah/witness patterns?
r = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Kingdom Hall%'").fetchone()[0]
print(f"Kingdom Hall in name (all sources): {r}")

r = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%CONGREGATION OF%' AND name LIKE '%JEHOVAH%'").fetchone()[0]
print(f"Congregation of Jehovah (all): {r}")

# check if overture has a brands column
r = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%' LIMIT 3").fetchall()
print(f"\nSample overture rows:")
for row in cur.execute("SELECT name, source FROM churches WHERE source LIKE '%overture%' LIMIT 5").fetchall():
    print(f"  {row[0][:50]:50s} [{row[1]}]")

# Check overture source values
for row in cur.execute("SELECT DISTINCT source FROM churches WHERE source LIKE '%overture%'").fetchall():
    print(f"  Source: {row[0]}")

db.close()

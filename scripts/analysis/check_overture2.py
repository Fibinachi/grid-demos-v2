import sqlite3
db = sqlite3.connect('churches.db')
cur = db.cursor()

# Check schema
cols = cur.execute("PRAGMA table_info(churches)").fetchall()
print("Schema columns:")
for c in cols:
    print(f'  {c[1]:30s} {c[2]:20s}')

print()

# Check Overture sources
rows = cur.execute("SELECT source, COUNT(*) FROM churches WHERE source LIKE '%overture%' GROUP BY source").fetchall()
print("Overture sources in DB:")
for r in rows:
    print(f'  {r[0]}: {r[1]}')

print()

# Check for JW patterns in all data
total_db = cur.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"Total records in DB: {total_db}")

# What columns might have brand/denomination info
for col in ['denomination', 'category', 'subcategory', 'brand', 'tags']:
    try:
        rows = cur.execute(f"SELECT {col}, COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != '' GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 5").fetchall()
        if rows:
            print(f"\n{col} values (top 5):")
            for r in rows:
                print(f'  {str(r[0])[:40]:40s}: {r[1]}')
    except:
        print(f"\n{col}: column does not exist")

db.close()

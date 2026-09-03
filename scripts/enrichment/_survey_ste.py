"""Survey all STE (abbreviated Sainte) patterns in church names."""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')

# 1. STE as standalone token in name
print("=== ' STE ' (abbreviated Sainte, standalone) in names ===")
c = db.execute("""
    SELECT name, COUNT(*) as cnt FROM churches
    WHERE name LIKE '% STE %' AND name NOT LIKE '%SAULT%'
    GROUP BY name ORDER BY cnt DESC LIMIT 30
""")
total = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE name LIKE '% STE %' AND name NOT LIKE '%SAULT%'
""").fetchone()[0]
print(f"Total records: {total:,}")
for name, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {name[:90]}")

# 2. STE. with period
print()
print("=== 'STE.' (with period) in names ===")
c = db.execute("""
    SELECT name, COUNT(*) as cnt FROM churches
    WHERE name LIKE '% STE.%' AND name NOT LIKE '%SAULT%'
    GROUP BY name ORDER BY cnt DESC LIMIT 20
""")
total = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE name LIKE '% STE.%' AND name NOT LIKE '%SAULT%'
""").fetchone()[0]
print(f"Total records: {total:,}")
for name, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {name[:90]}")

# 3. City contains STE
print()
print("=== City contains 'SAULT STE' ===")
c = db.execute("""
    SELECT city, state, country, COUNT(*) as cnt FROM churches
    WHERE city LIKE '%SAULT%STE%'
    GROUP BY city, state ORDER BY cnt DESC LIMIT 15
""")
for city, state, country, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {city}, {state} {country}")

print()
print("=== City contains 'STE ' (STE standalone in city) ===")
c = db.execute("""
    SELECT city, state, country, COUNT(*) as cnt FROM churches
    WHERE city LIKE '% STE %' AND city NOT LIKE '%SAULT%'
    GROUP BY city, state ORDER BY cnt DESC LIMIT 20
""")
for city, state, country, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {city}, {state} {country}")

# 4. How many would be affected by a STE -> SAINTE rule?
# Records where STE appears after SAULT
print()
print("=== SAULT STE in names (detailed) ===")
c = db.execute("""
    SELECT name, COUNT(*) as cnt FROM churches
    WHERE name LIKE '%SAULT%STE%'
    GROUP BY name ORDER BY cnt DESC
""")
for name, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {name[:90]}")

# 5. How many already have SAINTE?
print()
print("=== Already-expanded SAINTE in names ===")
c = db.execute("""
    SELECT name, COUNT(*) as cnt FROM churches
    WHERE name LIKE '%SAINTE%'
    GROUP BY name ORDER BY cnt DESC LIMIT 20
""")
total = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%SAINTE%'").fetchone()[0]
print(f"Total records: {total:,}")
for name, cnt in c.fetchall():
    print(f"  [{cnt:4d}] {name[:90]}")

db.close()

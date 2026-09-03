"""Quick overall Catholic counts."""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f'Total churches: {total:,}')

for col, val in [('faith', 'christian'), ('legacy', 'Catholic'), 
                  ('tradition', 'Catholic Churches'), ('tradition', 'Catholic')]:
    c = db.execute(f"SELECT COUNT(*) FROM churches WHERE {col}=?", (val,)).fetchone()[0]
    print(f'  {col} = {val}: {c:,}')

# Broader
c = db.execute("SELECT COUNT(*) FROM churches WHERE tradition LIKE '%Catholic%'").fetchone()[0]
print(f'  tradition LIKE "%Catholic%": {c:,}')

c = db.execute("SELECT COUNT(*) FROM churches WHERE legacy = 'Catholic'").fetchone()[0]
print(f'  legacy = Catholic: {c:,}')

# Combined Catholic
c = db.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE legacy = 'Catholic' OR tradition LIKE '%Catholic%'
""").fetchone()[0]
print(f'  legacy=Catholic OR tradition LIKE Catholic: {c:,}')

# FTLD cascade violations (Catholic-specific)
print('\n=== FTLD cascade for Catholic entries ===')
for desc, sql in [
    ("legacy=Catholic, faith missing", 
     "SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND (faith IS NULL OR faith='')"),
    ("legacy=Catholic, tradition missing",
     "SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND (tradition IS NULL OR tradition='')"),
    ("tradition LIKE Catholic, legacy missing",
     "SELECT COUNT(*) FROM churches WHERE tradition LIKE '%Catholic%' AND (legacy IS NULL OR legacy='')"),
    ("tradition LIKE Catholic, faith missing", 
     "SELECT COUNT(*) FROM churches WHERE tradition LIKE '%Catholic%' AND (faith IS NULL OR faith='')"),
]:
    c = db.execute(sql).fetchone()[0]
    print(f'  {desc}: {c:,}')

db.close()

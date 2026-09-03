"""Search for FLTD across all text columns"""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

for col in ['denomination', 'tradition', 'legacy', 'faith', 'name']:
    c.execute(f"SELECT DISTINCT {col} FROM churches WHERE {col} LIKE ?", (f'%FLD%',))
    for r in c.fetchall():
        if r[0]: print(f"{col} (FLD): {r[0]}")
    c.execute(f"SELECT DISTINCT {col} FROM churches WHERE {col} LIKE ?", (f'%FLT%',))
    for r in c.fetchall():
        if r[0]: print(f"{col} (FLT): {r[0]}")

# Also search taxonomy table
c.execute("SELECT name, full_path FROM taxonomy WHERE name LIKE '%FLT%' OR full_path LIKE '%FLT%'")
for r in c.fetchall():
    print(f"taxonomy: {r[0]} ({r[1]})")

# Maybe user means FTLD? (typo rearrangement)
for pat in ['FTLD', 'FDLT', 'LDFT']:
    c.execute("SELECT DISTINCT denomination FROM churches WHERE denomination LIKE ?", (f'%{pat}%',))
    for r in c.fetchall():
        if r[0]: print(f"denom ({pat}): {r[0]}")

db.close()

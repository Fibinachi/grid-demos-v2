"""Check DB schema - what columns exist"""
import sqlite3, os
db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "churches.db")
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("PRAGMA table_info(churches)")
cols = cur.fetchall()
print(f"Columns in churches table ({len(cols)}):")
for c in cols:
    print(f"  {c[1]:25} {c[2]:15}")
conn.close()

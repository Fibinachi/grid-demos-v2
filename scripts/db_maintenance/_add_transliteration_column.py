"""Add name_transliterated column to churches table."""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
cur = db.execute("PRAGMA table_info(churches)")
cols = [c[1] for c in cur.fetchall()]
if 'name_transliterated' not in cols:
    db.execute("ALTER TABLE churches ADD COLUMN name_transliterated TEXT")
    db.commit()
    print("Added name_transliterated column")
else:
    print("name_transliterated column already exists")
db.close()

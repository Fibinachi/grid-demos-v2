import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')
sql = db.execute("SELECT sql FROM sqlite_master WHERE type='view' AND name='v_churches'").fetchone()[0]
print(sql)
db.close()

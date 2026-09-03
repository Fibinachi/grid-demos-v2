import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    cnt = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {cnt:,} rows")
db.close()

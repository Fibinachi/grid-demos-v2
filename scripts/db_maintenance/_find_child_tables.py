"""Find tables with church_id column."""
from gw_db import connect
db = connect()
c = db.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for row in c.fetchall():
    tbl = row[0]
    c2 = db.cursor()
    c2.execute(f"PRAGMA table_info({tbl})")
    cols = [r[1] for r in c2.fetchall()]
    if 'church_id' in cols:
        print(tbl)
db.close()

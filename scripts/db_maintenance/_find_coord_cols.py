"""Find coordinate column names in churches table."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
c.execute("PRAGMA table_info(churches)")
for r in c.fetchall():
    name = r[1]
    if any(x in name.lower() for x in ['lat','lon','gps','coord','longitude','latitude']):
        print(f"  {name:25s} type={r[2]:15s} nullable={not r[3]}")
conn.close()

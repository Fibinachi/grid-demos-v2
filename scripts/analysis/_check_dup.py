"""Compare duplicate entries 2324230 and 3718835."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

for id_ in [2324230, 3718835]:
    c.execute("SELECT * FROM churches WHERE id=?", (id_,))
    cols = [d[1] for d in c.description]
    r = c.fetchone()
    print(f"=== ID {id_} ===")
    for i, col in enumerate(cols):
        print(f"  {col:30s} = {r[i]}")
    print()

conn.close()

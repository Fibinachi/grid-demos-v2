"""Revert MARKET SAINT false positive."""
import sqlite3
db = sqlite3.connect(r'E:\grid\churches.db')
cur = db.execute("SELECT rowid, name FROM churches WHERE name LIKE '%MARKET SAINT PRESBYTERIAN%'")
rows = cur.fetchall()
for r, n in rows:
    new_name = n.replace('SAINT', 'ST')
    print(f"  Reverting: {n} -> {new_name}")
    db.execute("UPDATE churches SET name = ? WHERE rowid = ?", (new_name, r))
db.commit()
count = len(rows)
db.close()
print(f"Reverted {count} records.")

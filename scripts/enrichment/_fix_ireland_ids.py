"""Fix NULL IDs for Ireland records."""
import sys; sys.path.insert(0, r'E:\grid')
import sqlite3
from gw_db import connect

# Use direct sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM churches").fetchone()[0]
nulls = conn.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"Max id: {max_id}, Null ids: {nulls}")

null_records = conn.execute("SELECT rowid FROM churches WHERE id IS NULL ORDER BY rowid").fetchall()
next_id = max_id + 1
for (rowid,) in null_records:
    conn.execute("UPDATE churches SET id = ? WHERE rowid = ?", (next_id, rowid))
    next_id += 1

conn.commit()
still_null = conn.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"Fixed {len(null_records)}, Still NULL: {still_null}")
conn.close()

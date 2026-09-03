"""Fix NULL id values by assigning unique sequential IDs."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Check current state
max_id = conn.execute("SELECT MAX(id) FROM churches").fetchone()[0] or 0
null_count = conn.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
total = conn.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"Max current id: {max_id}")
print(f"NULL id records: {null_count}")
print(f"Total records: {total}")

# Assign new IDs starting from max_id + 1
next_id = max_id + 1
assigned = 0

# Get all NULL-id records ordered by rowid
null_records = conn.execute(
    "SELECT rowid FROM churches WHERE id IS NULL ORDER BY rowid"
).fetchall()

for (rowid,) in null_records:
    conn.execute("UPDATE churches SET id = ? WHERE rowid = ?", (next_id, rowid))
    next_id += 1
    assigned += 1
    
    if assigned % 500 == 0:
        conn.commit()
        print(f"  Assigned {assigned}...")

conn.commit()

# Verify
still_null = conn.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL").fetchone()[0]
print(f"\nAssigned: {assigned}")
print(f"Still NULL: {still_null}")
print(f"New max id: {next_id - 1}")
conn.close()

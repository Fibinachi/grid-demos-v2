"""Fix NULL id values in inserted NHL records."""
import sqlite3
conn = sqlite3.connect("churches.db")
c = conn.cursor()

# Find records with NULL id
c.execute("SELECT rowid, name, city, state FROM churches WHERE id IS NULL")
rows = c.fetchall()
print(f"Found {len(rows)} records with NULL id")

# Get current max id
c.execute("SELECT MAX(id) FROM churches")
max_id = c.fetchone()[0] or 0
print(f"Current max id: {max_id}")

# Assign IDs starting from max_id + 1
next_id = max_id + 1
for r in rows:
    rowid, name, city, state = r
    c.execute("UPDATE churches SET id=? WHERE rowid=?", (next_id, rowid))
    print(f"  rowid={rowid} -> id={next_id} | {str(name or '')[:50]} | {str(city or '')} | {state}")
    next_id += 1

conn.commit()
print(f"\nFixed. Next available id: {next_id}")

# Verify
c.execute("SELECT COUNT(*) FROM churches WHERE id IS NULL")
remaining = c.fetchone()[0]
print(f"Records still with NULL id: {remaining}")

conn.close()

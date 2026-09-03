import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

# Remove short entries (< 10 chars) - these are incomplete
conn.execute("DELETE FROM wpa_churches WHERE LENGTH(church_name) < 10")

# Show what was removed
print(f"Removed entries. Remaining: {conn.execute('SELECT COUNT(*) FROM wpa_churches').fetchone()[0]}")

# Show sample short entries that were removed
print("\n=== Sample removed entries ===")
for row in conn.execute("SELECT church_name FROM wpa_churches_backup LIMIT 10").fetchall():
    print(f"  {row[0]}")

conn.close()
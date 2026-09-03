import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

# Count before
before = conn.execute("SELECT COUNT(*) FROM wpa_churches").fetchone()[0]
print(f"Before cleanup: {before} entries")

# Remove entries that are too short or contain obvious junk
conn.execute("""DELETE FROM wpa_churches WHERE 
    LENGTH(church_name) < 10 OR
    church_name LIKE '%god only%' OR
    church_name LIKE '%assembly of %church%'""")

after = conn.execute("SELECT COUNT(*) FROM wpa_churches").fetchone()[0]
print(f"After cleanup: {after} entries")
print(f"Removed: {before - after} entries")

conn.commit()
conn.close()
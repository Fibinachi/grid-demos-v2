import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print("=== FINAL WPA DATABASE ===")
print(f"Total entries: {conn.execute('SELECT COUNT(*) FROM wpa_churches').fetchone()[0]}")

print("\nBy state:")
for state, count in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state ORDER BY COUNT(*) DESC").fetchall():
    print(f"  {state}: {count}")

print("\n=== Sample final entries ===")
for row in conn.execute("SELECT state, church_name FROM wpa_churches WHERE LENGTH(church_name) BETWEEN 15 AND 50 LIMIT 20").fetchall():
    print(f"  {row[0]}: {row[1][:60]}")

conn.close()
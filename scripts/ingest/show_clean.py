import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print("=== Sample clean entries ===")
for row in conn.execute("SELECT church_name FROM wpa_churches WHERE LENGTH(church_name) BETWEEN 10 AND 50 LIMIT 30").fetchall():
    print(f"  {row[0]}")

print(f"\nTotal: {conn.execute('SELECT COUNT(*) FROM wpa_churches').fetchone()[0]} entries")
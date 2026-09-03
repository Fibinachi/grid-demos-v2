import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print("=== Sample entries by state ===")
for state in ['AR', 'MN', 'ME', 'NM', 'DE', 'DC', 'ID']:
    row = conn.execute(f"SELECT church_name FROM wpa_churches WHERE state='{state}' LIMIT 5").fetchone()
    if row:
        print(f"\n{state}:")
        for r in conn.execute(f"SELECT church_name FROM wpa_churches WHERE state='{state}' LIMIT 5").fetchall():
            print(f"  {r[0][:70]}")

print(f"\n=== Totals ===")
for row in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state ORDER BY COUNT(*) DESC").fetchall():
    print(f"  {row[0]}: {row[1]}")
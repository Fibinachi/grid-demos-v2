import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print('=== Arkansas sample ===')
for row in conn.execute("SELECT church_name FROM wpa_churches WHERE state='AR' LIMIT 20").fetchall():
    print(f'  {row[0]}')

print('\n=== All states count ===')
for row in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state").fetchall():
    print(f'  {row[0]}: {row[1]}')
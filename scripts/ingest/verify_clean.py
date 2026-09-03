import sqlite3

conn = sqlite3.connect('E:/grid/wpa.db')

print('=== Final cleaned Arkansas entries ===')
for row in conn.execute("SELECT church_name FROM wpa_churches WHERE state='AR' LIMIT 20").fetchall():
    print(f'  {row[0][:60]}')

print(f'\nTotal entries: {conn.execute("SELECT COUNT(*) FROM wpa_churches").fetchone()[0]}')
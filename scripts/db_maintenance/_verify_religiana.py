"""Verify imported Religiana data."""
import sqlite3
conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
c.execute("SELECT id, name, city, country, latitude, longitude, source FROM churches WHERE source='religiana'")
rows = c.fetchall()
print(f'{len(rows)} religiana entries:')
for r in rows[:10]:
    print(f'  {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]},{r[5]}')
if len(rows) > 10:
    print(f'  ... and {len(rows)-10} more')
conn.close()

import sqlite3
conn = sqlite3.connect('churches.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM anglican_hierarchy')
print(f'anglican_hierarchy rows: {cur.fetchone()[0]}')

cur.execute('SELECT COUNT(*) FROM churches WHERE faith = "Anglican"')
print(f'Anglican churches in DB: {cur.fetchone()[0]}')

cur.execute('SELECT COUNT(*) FROM churches WHERE tradition LIKE "%Episcopal%"')
print(f'Episcopal tradition churches: {cur.fetchone()[0]}')

conn.close()
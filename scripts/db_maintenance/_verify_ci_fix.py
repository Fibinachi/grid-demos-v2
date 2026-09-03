"""Verify CI fixes."""
import sqlite3
conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
c.execute("SELECT rowid, name, faith, faith_tradition FROM churches WHERE rowid IN (1805214, 2844002)")
for r in c.fetchall():
    print(f'  rowid={r[0]}: {r[1]} | faith={r[2]} | ft={r[3]}')
conn.close()

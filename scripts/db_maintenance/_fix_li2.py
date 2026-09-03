import sqlite3
conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
c.execute("UPDATE churches SET denomination='Roman Catholic' WHERE country='LI' AND name='Vaduz Cathedral'")
c.execute("UPDATE churches SET denomination='Protestant' WHERE country='LI' AND name LIKE '%Wartau%'")
conn.commit()
c.execute("SELECT name, denomination, city FROM churches WHERE country='LI' ORDER BY denomination, name")
for r in c.fetchall():
    print(f"  {r[0][:45]:45s} | {str(r[1]):20s} | {r[2]}")
conn.close()

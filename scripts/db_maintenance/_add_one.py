"""Quickly add individual churches. Usage: python _add_one.py "Name" "City" "ST" "Address" """
import sys, sqlite3
name, city, state = sys.argv[1], sys.argv[2], sys.argv[3]
addr = sys.argv[4] if len(sys.argv) > 4 else ''
db = sqlite3.connect(r'E:\grid\churches.db')
c = db.cursor()
ex = c.execute("SELECT id FROM churches WHERE name=? AND city=? AND state=?", (name, city, state)).fetchone()
if ex: print(f'EXISTS #{ex[0]}: {name}')
else:
    mid = c.execute('SELECT MAX(id) FROM churches').fetchone()[0] + 1
    c.execute("INSERT INTO churches(id,name,city,state,country,address,faith,culture_id,landmark_type,source) VALUES(?,?,?,?,'US',?,'Christian',555,'church','manual_import')", (mid, name, city, state, addr))
    db.commit(); print(f'ADDED #{mid}: {name}')
db.close()

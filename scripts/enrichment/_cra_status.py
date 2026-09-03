import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
lapsed = db.execute("SELECT COUNT(*) FROM churches WHERE notes LIKE '%lapsed%'").fetchone()[0]
ca = db.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
tot = db.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
cra11 = db.execute("SELECT COUNT(*) FROM churches WHERE source='cra_2011'").fetchone()[0]
cra18 = db.execute("SELECT COUNT(*) FROM churches WHERE source='cra_2018'").fetchone()[0]
print(f'Tagged cra_registration_lapsed: {lapsed:,}')
print(f'CRA 2011 churches: {cra11:,}')
print(f'CRA 2018 churches: {cra18:,}')
print(f'Canada total: {ca:,}')
print(f'All churches: {tot:,}')
db.close()

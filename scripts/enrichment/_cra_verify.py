import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
total = db.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
ca = db.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
cra = db.execute("SELECT COUNT(*) FROM churches WHERE source='cra_2018'").fetchone()[0]
by_cat = db.execute("SELECT cra_category, COUNT(*) FROM churches WHERE source='cra_2018' GROUP BY cra_category ORDER BY COUNT(*) DESC").fetchall()
print(f'Total churches: {total:,}')
print(f'Canada total: {ca:,}')
print(f'CRA 2018: {cra:,}')
print(f'By category:')
names = {30:'Christian', 40:'Muslim', 50:'Jewish', 60:'Buddhist/Sikh', 90:'Religious Ed'}
for cat, cnt in by_cat:
    print(f'  Cat {cat} ({names.get(cat,"?")}): {cnt:,}')
db.close()

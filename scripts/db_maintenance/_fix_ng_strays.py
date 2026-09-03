import sqlite3
db = sqlite3.connect('e:/grid/churches.db')

# Thai temple "Wat Khiri Nak Ratnaram, Lopburi Province" — GPS-misplaced from Thailand
db.execute("UPDATE churches SET country='TH', state=NULL WHERE country='NG' AND faith='Buddhist'")
n = db.total_changes
print(f'Moved {n} Buddhist entry to Thailand')

# Cameroon shrine
db.execute("UPDATE churches SET country='CM' WHERE country='NG' AND name='Nninong shrine'")
n2 = db.total_changes
print(f'Moved {n2} shrine to Cameroon')

db.commit()

# Final Nigeria state
print('\n=== Final Nigeria ===')
for r in db.execute("SELECT faith, COUNT(*) n FROM churches WHERE country='NG' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r[0]}: {r[1]:,}')

total = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG'").fetchone()[0]
print(f'\nTotal Nigeria: {total:,}')
db.close()

import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
cnt = db.execute("SELECT COUNT(*) FROM churches WHERE source='cra_2011'").fetchone()[0]
print(f'Deleting {cnt:,} CRA 2011 records...')
db.execute("DELETE FROM churches WHERE source='cra_2011'")
db.execute("DELETE FROM provenance_log WHERE source='cra_2011'")
db.commit()
print(f'Done. Total churches: {db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]:,}')
db.close()

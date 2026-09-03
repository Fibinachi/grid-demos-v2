"""Drop the unused subtradition column from churches table."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

print('Dropping subtradition column...')
db.execute('ALTER TABLE churches DROP COLUMN subtradition')
db.commit()

cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()]
print(f'Column dropped. Remaining columns: {len(cols)}')
print(f'subtradition still present: {"subtradition" in cols}')
db.close()

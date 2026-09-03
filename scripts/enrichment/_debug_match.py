"""Debug match performance for Gloucester, MA."""
import sqlite3, time, re
from difflib import SequenceMatcher

db = sqlite3.connect('e:/grid/churches.db')
db.execute('PRAGMA journal_mode=WAL')

# Check Gloucester count
t0 = time.time()
count = db.execute("SELECT COUNT(*) FROM churches WHERE city='Gloucester'").fetchone()[0]
print(f'Gloucester churches in GRID: {count} ({time.time()-t0:.2f}s)')

# Test match speed
t0 = time.time()
rows = list(db.execute("SELECT id, name FROM churches WHERE city='Gloucester' LIMIT 100"))
print(f'Query 100 rows: {time.time()-t0:.2f}s')

# Test SequenceMatcher speed
test_name = "First Baptist Church"
t0 = time.time()
for row in rows:
    score = SequenceMatcher(None, test_name.lower(), row[1].lower()).ratio()
print(f'{len(rows)} comparisons: {time.time()-t0:.2f}s')

db.close()
print('Done')

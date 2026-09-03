import sqlite3, time
db = sqlite3.connect('e:/grid/churches.db')
# Check name indexes
rows = db.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='churches'").fetchall()
print('Indexes on churches:')
for r in rows:
    print(f'  {r[0]}')

# Check LIKE performance
t0 = time.time()
rows = db.execute("SELECT id, name, city, state FROM churches WHERE name LIKE '%Baptist%' LIMIT 30").fetchall()
print(f'\nLIKE query: {time.time()-t0:.2f}s, {len(rows)} rows')

# Explain plan
for r in db.execute("EXPLAIN QUERY PLAN SELECT id,name,city,state FROM churches WHERE name LIKE '%Baptist%' LIMIT 30"):
    print(f'  PLAN: {r}')
db.close()

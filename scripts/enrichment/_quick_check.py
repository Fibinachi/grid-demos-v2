"""Quick integrity check."""
import sys; sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')
print('id col:', conn.execute('PRAGMA table_info(churches)').fetchall()[0])
print('Null IDs:', conn.execute('SELECT COUNT(*) FROM churches WHERE id IS NULL').fetchone()[0])
print('Total:', conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0])

rows = conn.execute("SELECT rowid, id, name FROM churches WHERE name LIKE '%ADAMS GEORGE%'").fetchall()
print('ADAMS GEORGE:', rows)

print('\nBy source:')
for s in conn.execute("SELECT source, COUNT(*) FROM churches GROUP BY source ORDER BY COUNT(*) DESC").fetchall():
    print(f'  {s[0] or "NULL"}: {s[1]}')

# Sample Boston-assessed records
print('\nSample boston_property_assessment records:')
for r in conn.execute("SELECT rowid, id, name, faith, city, boston_pid FROM churches WHERE source='boston_property_assessment' LIMIT 5").fetchall():
    print(f'  rowid={r[0]} id={r[1]} name={r[2][:40]} faith={r[3]} city={r[4]} pid={r[5]}')

conn.close()

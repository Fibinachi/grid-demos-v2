"""Verify SA denom fix results."""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

for label, col, val in [
    ("denom='Salvation Army'", "denomination_affiliation", 'Salvation Army'),
    ("denom='The Salvation Army'", "denomination_affiliation", 'The Salvation Army'),
    ("subtradition='Salvationist'", "subtradition", 'Salvationist'),
    ("family='Holiness Churches'", "family", 'Holiness Churches'),
]:
    c = db.execute("SELECT COUNT(*) FROM churches WHERE ? = ?", (col, val)).fetchone()[0]
    print(f'{label}: {c:,}')

# Check sa_hierarchy count and denom in hierarchy
hier = db.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]
print(f'\nsa_hierarchy total: {hier:,}')

# Sample name patterns in sa_hierarchy
print('\nSample sa_hierarchy names (first 10):')
for r in db.execute("SELECT name FROM sa_hierarchy LIMIT 10"):
    print(f'  {r[0]}')

# Check provenance_log schema
print('\nprovenance_log columns:')
for c in db.execute('PRAGMA table_info(provenance_log)'):
    print(f'  {c[1]} ({c[2]})')

db.close()

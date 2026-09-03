"""Check church_contact_values schema."""
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# Columns
cols = conn.execute('PRAGMA table_info(church_contact_values)').fetchall()
print('church_contact_values columns:')
for c in cols:
    print(f'  {c[1]}: {c[2]} nullable={not c[3]} default={c[4]} pk={c[5]}')

# CREATE TABLE SQL
schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='church_contact_values'").fetchone()
print(f'\nCREATE TABLE:\n{schema[0]}')

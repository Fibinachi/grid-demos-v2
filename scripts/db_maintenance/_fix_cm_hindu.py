"""Fix mislocated Gaudiya Math Patna — was in Cameroon, should be Patna, India."""
import sqlite3, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))

DB = 'E:/grid/churches.db'
ROWID = 1735781  # Gaudiya Math Patna

conn = sqlite3.connect(DB)
c = conn.cursor()

# Before
old = c.execute('SELECT rowid, name, latitude, longitude, country FROM churches WHERE rowid=?', (ROWID,)).fetchone()
print(f'Before: {old}')

# Update to Patna, Bihar, India
c.execute(
    'UPDATE churches SET country=?, latitude=?, longitude=?, city=?, state=? WHERE rowid=?',
    ('IN', 25.5941, 85.1376, 'Patna', 'Bihar', ROWID)
)

# Provenance — log per-field changes
has_echg = c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='enrichment_change_log'"
).fetchone()
if has_echg:
    for field, old_val, new_val in [
        ('country', 'CM', 'IN'),
        ('latitude', '3.837878', '25.5941'),
        ('longitude', '12.340565', '85.1376'),
        ('city', None, 'Patna'),
        ('state', None, 'Bihar'),
    ]:
        c.execute(
            'INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) VALUES (?,?,?,?,?,datetime("now"))',
            (ROWID, field, old_val, new_val, 'manual_fix_cm_hindu')
        )

after = c.execute('SELECT rowid, name, latitude, longitude, country, city, state FROM churches WHERE rowid=?', (ROWID,)).fetchone()
print(f'After:  {after}')
conn.commit()
conn.close()
print('Done.')

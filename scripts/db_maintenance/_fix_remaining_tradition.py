"""Fix remaining Catholic entries missing tradition."""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

now = datetime.now().isoformat()

# Set tradition for all legacy=Catholic entries that are missing it
print('Setting tradition=Catholic Churches for all legacy=Catholic entries missing tradition...')
db.execute("""
    UPDATE churches 
    SET tradition = 'Catholic Churches'
    WHERE legacy = 'Catholic'
      AND (tradition IS NULL OR tradition = '')
""")
db.commit()
fixed = db.execute("SELECT changes()").fetchone()[0]
print(f'  {fixed:,} entries updated')

# Also ensure faith=christian for all legacy=Catholic entries
print('\nEnsuring faith=christian...')
db.execute("""
    UPDATE churches
    SET faith = 'christian'
    WHERE legacy = 'Catholic'
      AND (faith IS NULL OR faith = '' OR faith != 'christian')
""")
db.commit()
fixed2 = db.execute("SELECT changes()").fetchone()[0]
print(f'  {fixed2:,} entries updated')

# Verify
print('\nVerification:')
for q, l in [
    ("SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND tradition='Catholic Churches'", "legacy=Catholic + tradition=Catholic Churches"),
    ("SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND (tradition IS NULL OR tradition='')", "legacy=Catholic but tradition missing"),
    ("SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND faith='christian'", "legacy=Catholic + faith=christian"),
]:
    c = db.execute(q).fetchone()[0]
    print(f'  {l}: {c:,}')

# Log provenance
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_tradition_fix', '_fix_remaining_tradition.py', now, now,
     fixed, 'tradition', 'completed',
     f'Set tradition=Catholic Churches for {fixed} entries missing it'))
db.commit()

print('\nDone!')
db.close()

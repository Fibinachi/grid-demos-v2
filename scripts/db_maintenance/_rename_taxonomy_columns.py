"""Rename taxonomy columns:
   religion_type -> faith
   tradition_legacy -> legacy
   family -> tradition
   denomination_affiliation -> denomination
"""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

# Check for any objects referencing old column names
print('Checking for dependencies...')
views = db.execute("SELECT name, sql FROM sqlite_master WHERE type='view'").fetchall()
triggers = db.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'").fetchall()
indexes = db.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall()

print(f'  Views: {len(views)}')
print(f'  Triggers: {len(triggers)}')
print(f'  Named indexes: {len(indexes)}')

# Save view definitions for recreation
view_defs = {}
for v in views:
    if 'religion_type' in v[1] or 'tradition_legacy' in v[1] or 'family' in v[1] or 'denomination_affiliation' in v[1]:
        view_defs[v[0]] = v[1]
        print(f'  View {v[0]} references old columns')

if view_defs:
    print(f'\nDropping affected views...')
    for vname in view_defs:
        db.execute(f'DROP VIEW IF EXISTS {vname}')
        print(f'  Dropped {vname}')

# Rename columns
print('\nRenaming columns...')
renames = [
    ('religion_type', 'faith'),
    ('tradition_legacy', 'legacy'),
    ('family', 'tradition'),
    ('denomination_affiliation', 'denomination'),
]

for old, new in renames:
    print(f'  {old} -> {new}')
    db.execute(f'ALTER TABLE churches RENAME COLUMN {old} TO {new}')
    db.commit()

# Recreate views
print('\nRecreating views...')
for vname, sql in view_defs.items():
    # Replace old column names with new ones in the view SQL
    new_sql = sql
    new_sql = new_sql.replace('c.religion_type', 'c.faith')
    new_sql = new_sql.replace('c.tradition_legacy', 'c.legacy')
    new_sql = new_sql.replace('c.family', 'c.tradition')
    new_sql = new_sql.replace('c.denomination_affiliation', 'c.denomination')
    # Also replace bare column references (for the SELECT list)
    new_sql = new_sql.replace(', c.family,', ', c.tradition,')
    new_sql = new_sql.replace(', c.religion_type,', ', c.faith,')
    new_sql = new_sql.replace(', c.denomination_affiliation,', ', c.denomination,')
    new_sql = new_sql.replace(', c.tradition_legacy,', ', c.legacy,')
    db.execute(new_sql)
    print(f'  Recreated {vname}')

db.commit()

# Verify
cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()]
print(f'\nVerification:')
print(f'  Total columns: {len(cols)}')
expected = {'faith', 'legacy', 'tradition', 'denomination'}
for name in expected:
    present = name in cols
    print(f'  {name}: {"✅" if present else "❌"}')

# Verify view works
for vname in view_defs:
    try:
        r = db.execute(f'SELECT COUNT(*) FROM {vname}').fetchone()
        print(f'  View {vname}: ✅ ({r[0]:,} rows)')
    except Exception as e:
        print(f'  View {vname}: ❌ {e}')

# Quick sample
print(f'\nSA entry sample:')
r = db.execute("""
    SELECT faith, legacy, tradition, denomination
    FROM churches
    WHERE name LIKE '%Salvation Army%'
    LIMIT 3
""").fetchall()
for row in r:
    print(f'  {row[0]} -> {row[1]} -> {row[2]} -> {row[3]}')

# Count SA with correct taxonomy
c = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Salvation Army%' OR name LIKE '%Ejercito de Salvacion%')
      AND faith = 'christian'
      AND legacy = 'Protestant'
      AND tradition = 'Holiness Churches'
      AND denomination = 'Salvation Army'
""").fetchone()[0]
print(f'SA entries with full taxonomy: {c:,}')

db.close()
print('\nDone!')

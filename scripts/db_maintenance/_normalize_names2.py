"""
Normalize ALL church names: drop leading/trailing THE, collapse spaces, UPPERCASE.
"""
import sqlite3, re
from datetime import datetime

conn = sqlite3.connect('churches.db')
conn.execute("PRAGMA busy_timeout=30000")
now = datetime.now().isoformat()
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

print(f'Total churches: {total:,}')

# 1. Drop leading "The " / "THE "
print('\n=== 1. Drop leading THE ===')
rows = conn.execute("SELECT id, name FROM churches WHERE UPPER(name) LIKE 'THE %'").fetchall()
print(f'  Found: {len(rows):,}')
for r in rows[:5]:
    print(f'    "{r[1]}"')
batch = [(re.sub(r'^the\s+', '', r[1], flags=re.IGNORECASE), r[0]) for r in rows]
conn.executemany("UPDATE churches SET name=? WHERE id=?", batch)
print(f'  Fixed: {len(batch):,}')

# 2. Drop trailing THE artifacts
print('\n=== 2. Drop trailing THE artifacts ===')
rows = conn.execute("SELECT id, name FROM churches WHERE UPPER(name) LIKE '% THE'").fetchall()
print(f'  Found: {len(rows):,}')
for r in rows[:5]:
    print(f'    "{r[1]}"')
batch = [(re.sub(r'\s+the$', '', r[1], flags=re.IGNORECASE), r[0]) for r in rows]
conn.executemany("UPDATE churches SET name=? WHERE id=?", batch)
print(f'  Fixed: {len(batch):,}')

# 3. Collapse multiple spaces
print('\n=== 3. Collapse double spaces ===')
rows = conn.execute("SELECT id, name FROM churches WHERE name LIKE '%  %'").fetchall()
print(f'  Found: {len(rows):,}')
fixed = 0
for r in rows:
    new = re.sub(r'\s{2,}', ' ', r[1]).strip()
    if new != r[1]:
        conn.execute("UPDATE churches SET name=? WHERE id=?", (new, r[0]))
        fixed += 1
print(f'  Fixed: {fixed:,}')

# 4. Drop trailing periods (preserve INC., LLC., etc.)
print('\n=== 4. Drop trailing periods ===')
rows = conn.execute("""
    SELECT id, name FROM churches WHERE name LIKE '%.' 
    AND UPPER(name) NOT LIKE '%INC.' AND UPPER(name) NOT LIKE '%LLC.' 
    AND UPPER(name) NOT LIKE '%LTD.' AND UPPER(name) NOT LIKE '%CORP.'
    AND UPPER(name) NOT LIKE '%JR.' AND UPPER(name) NOT LIKE '%SR.' 
    AND UPPER(name) NOT LIKE '%DR.' AND UPPER(name) NOT LIKE '%U.S.%'
""").fetchall()
print(f'  Found: {len(rows):,}')
batch = [(r[1].rstrip('.'), r[0]) for r in rows]
conn.executemany("UPDATE churches SET name=? WHERE id=?", batch)
print(f'  Fixed: {len(batch):,}')

# 5. Drop trailing commas
print('\n=== 5. Drop trailing commas ===')
rows = conn.execute("SELECT id, name FROM churches WHERE name LIKE '%,'").fetchall()
print(f'  Found: {len(rows):,}')
batch = [(r[1].rstrip(',').strip(), r[0]) for r in rows]
conn.executemany("UPDATE churches SET name=? WHERE id=?", batch)
print(f'  Fixed: {len(batch):,}')

# 6. UPPERCASE everything
print('\n=== 6. UPPERCASE all names ===')
not_upper = conn.execute("SELECT COUNT(*) FROM churches WHERE name != UPPER(name)").fetchone()[0]
print(f'  Not uppercase: {not_upper:,} ({100*not_upper/total:.1f}%)')
conn.execute("UPDATE churches SET name = UPPER(name) WHERE name != UPPER(name)")
print(f'  All names now UPPERCASE')
conn.commit()

# Verify
print(f'\n=== VERIFICATION ===')
remaining_the = conn.execute("SELECT COUNT(*) FROM churches WHERE UPPER(name) LIKE 'THE %'").fetchone()[0]
print(f'  Leading THE remaining: {remaining_the}')
not_upper = conn.execute("SELECT COUNT(*) FROM churches WHERE name != UPPER(name)").fetchone()[0]
print(f'  Not uppercase: {not_upper}')

print('\n  Samples:')
for r in conn.execute("SELECT name, city, state, source FROM churches ORDER BY RANDOM() LIMIT 8").fetchall():
    print(f'    "{r[0][:50]:50s}"  {r[1]:15s} {r[2]}  ({r[3]})')

# Log
conn.execute("""
    INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
    VALUES (0, 'name_normalizer', 'uppercase_normalize', ?, ?)
""", (f'{total:,} churches: dropped THE, collapsed spaces, UPPERCASE', now))
conn.commit()

conn.close()
print('\nDone.')

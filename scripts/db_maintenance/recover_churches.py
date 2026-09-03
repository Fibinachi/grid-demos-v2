"""Resume recovery from corrupt DB. Saves previously recovered rows."""
import sqlite3, os, sys, time

CORRUPT = 'churches.db.corrupt_20260615'
TEMP = 'churches_recovering.db'
FINAL = 'churches.db'

if not os.path.exists(CORRUPT):
    print(f'ERROR: {CORRUPT} not found')
    sys.exit(1)

src = sqlite3.connect(CORRUPT, timeout=300)

# Check for existing partial recovery
if os.path.exists(TEMP):
    dst = sqlite3.connect(TEMP, timeout=300)
    dc = dst.cursor()
    dc.execute('SELECT COUNT(*) FROM churches')
    existing = dc.fetchone()[0]
    print(f'Resuming from {TEMP} ({existing:,} rows already recovered)')
else:
    dst = sqlite3.connect(TEMP, timeout=300)
    dc = dst.cursor()
    existing = 0
    # Create table
    sc = src.cursor()
    sc.execute('PRAGMA table_info(churches)')
    cols = [(r[1], r[2]) for r in sc.fetchall()]
    col_defs = ', '.join(f'"{c[0]}" {c[1]}' if c[1] else f'"{c[0]}"' for c in cols)
    dc.execute(f'CREATE TABLE churches ({col_defs})')
    dst.commit()
    print(f'Created churches table ({len(cols)} cols)')

sc = src.cursor()

# Get columns
sc.execute('PRAGMA table_info(churches)')
cols = [(r[1], r[2]) for r in sc.fetchall()]
col_names = [c[0] for c in cols]
col_quoted = ', '.join(f'"{c}"' for c in col_names)
ph = ', '.join(['?'] * len(cols))

# Resume from existing count
offset = existing
print(f'Starting from offset {offset:,}')
print(f'Copying row by row...')

added = 0
failed = 0
t0 = time.time()
last_report = 0

while True:
    # Try batch
    try:
        sc.execute(f'SELECT {col_quoted} FROM churches LIMIT 500 OFFSET {offset}')
        rows = sc.fetchall()
    except:
        # Corrupt page - skip entire batch
        failed += 500
        offset += 500
        dst.commit()
        print(f'  SKIPPED corrupt block at offset {offset-500:,} ({failed:,} bad total)', flush=True)
        continue
    
    else:
        if not rows:
            break
        
        for row in rows:
            try:
                dc.execute(f'INSERT INTO churches ({col_quoted}) VALUES ({ph})', row)
                added += 1
            except:
                failed += 1
        dst.commit()
        offset += len(rows)
    
    if added - last_report >= 1000:
        elapsed = time.time() - t0
        rate = added / elapsed if elapsed > 0 else 0
        total = existing + added
        size_mb = os.path.getsize(TEMP) / (1024*1024)
        print(f'  {total:,} total ({added:,} new, {failed:,} bad) | {rate:.0f} rows/s | {size_mb:.0f} MB', flush=True)
        last_report = added

elapsed = time.time() - t0
total = existing + added
print(f'\nDONE: {total:,} total ({added:,} new, {failed:,} bad) in {elapsed:.0f}s')

# Verify
dc.execute('PRAGMA integrity_check')
print(f'Integrity: {dc.fetchone()[0]}')

src.close()
dst.close()

# Replace
if os.path.exists(FINAL):
    os.remove(FINAL)
os.rename(TEMP, FINAL)
print(f'\n{FINAL}: {os.path.getsize(FINAL):,} bytes')


# Stats
db = sqlite3.connect(FINAL)
c = db.cursor()
c.execute('SELECT COUNT(*) FROM churches')
print(f'churches: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
print(f'websites: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
print(f'emails: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''")
print(f'denominated: {c.fetchone()[0]:,}')
db.close()
print('DONE.')

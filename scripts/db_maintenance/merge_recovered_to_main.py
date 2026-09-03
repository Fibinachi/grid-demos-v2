"""Merge recovered churches into main DB"""
import sqlite3, shutil, os
from datetime import datetime

RECOVERED = 'E:/grid/churches_recovered_all.db'
MAIN = 'E:/grid/churches.db'

# Backup
backup = f'E:/grid/churches_pre_merge_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
print(f'Backing up to {backup}...')
shutil.copy2(MAIN, backup)
print(f'Backup: {os.path.getsize(backup):,} bytes')

rec = sqlite3.connect(RECOVERED)
main = sqlite3.connect(MAIN)

rc = rec.cursor()
mc = main.cursor()

# Get existing IDs
mc.execute('SELECT id FROM churches')
main_ids = set(r[0] for r in mc.fetchall())
print(f'Main churches before merge: {len(main_ids):,}')

# Get recovered churches schema
rc.execute('PRAGMA table_info(churches)')
rec_cols = [r[1] for r in rc.fetchall()]
mc.execute('PRAGMA table_info(churches)')
main_cols = [r[1] for r in mc.fetchall()]

# Map matching columns
matching = [c for c in rec_cols if c in main_cols]
print(f'Matching columns: {len(matching)}/{len(rec_cols)}')

col_quoted = ', '.join(f'"{c}"' for c in matching)
ph = ', '.join(['?'] * len(matching))

# Iterate recovered and insert missing (NOT IN would exceed SQLite's 999-var limit)
print('Finding new churches to merge...')
rc.execute('SELECT id FROM churches')
all_rec_ids = [r[0] for r in rc.fetchall()]
new_ids = [i for i in all_rec_ids if i not in main_ids]
print(f'New churches to merge: {len(new_ids):,}')

if not new_ids:
    print('Nothing to merge!')
    rec.close()
    main.close()
    os.remove(backup)
    exit()

# Insert in batches
BATCH = 1000
added = 0
for i in range(0, len(new_ids), BATCH):
    batch = new_ids[i:i+BATCH]
    placeholders = ','.join('?' for _ in batch)
    rc.execute(f'SELECT {col_quoted} FROM churches WHERE id IN ({placeholders})', batch)
    rows = rc.fetchall()
    
    for row in rows:
        try:
            mc.execute(f'INSERT INTO churches ({col_quoted}) VALUES ({ph})', row)
            added += 1
        except Exception as e:
            pass  # skip duplicates/integrity errors
    
    main.commit()
    if (i // BATCH) % 10 == 0:
        print(f'  {i+len(batch):,}/{len(new_ids):,} ({added:,} inserted)', flush=True)

print(f'\nInserted: {added:,} new churches')
mc.execute('SELECT COUNT(*) FROM churches')
final_count = mc.fetchone()[0]
print(f'Total churches after merge: {final_count:,}')

# Integrity
mc.execute('PRAGMA integrity_check')
print(f'Integrity: {mc.fetchone()[0]}')

# Now merge enrichment tables that main DB is missing
print('\n=== Merging enrichment tables ===')
rc.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
rec_tables = set(r[0] for r in rc.fetchall())

mc.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
main_tables = set(r[0] for r in mc.fetchall())

# Tables to copy (enrichment tables not in main)
SKIP = {'churches', 'church_sources', 'church_staff', 'org_links', 
        'pss_schools', 'sources', 'provenance_log', 'org_officers',
        'lost_and_found', 'sqlite_sequence', 'sqlite_stat1',
        '_acs_temp', '_attendance_results', '_church_arena', '_county_denom_counts', 'arda_counts'}

for tbl in sorted(rec_tables - main_tables - SKIP):
    try:
        rc.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        cnt = rc.fetchone()[0]
        if cnt == 0:
            continue
        
        # Get schema
        rc.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{tbl}'")
        create_sql = rc.fetchone()[0]
        mc.execute(create_sql)
        
        # Copy data
        rc.execute(f'PRAGMA table_info("{tbl}")')
        cols = [r[1] for r in rc.fetchall()]
        col_quoted = ', '.join(f'"{c}"' for c in cols)
        ph = ', '.join(['?'] * len(cols))
        
        rc.execute(f'SELECT {col_quoted} FROM "{tbl}"')
        for row in rc.fetchall():
            mc.execute(f'INSERT INTO "{tbl}" ({col_quoted}) VALUES ({ph})', row)
        main.commit()
        print(f'  {tbl}: {cnt:,} rows copied')
    except Exception as e:
        print(f'  {tbl}: SKIPPED ({e})')

main.commit()
rec.close()

# Vacuum
print('\nVacuuming...')
main.execute('VACUUM')
main.close()

size = os.path.getsize(MAIN)
print(f'\n=== DONE ===')
print(f'churches.db: {size:,} bytes ({size/1024/1024:.0f} MB)')
print(f'Churches: {final_count:,}')
print(f'Backup: {backup}')

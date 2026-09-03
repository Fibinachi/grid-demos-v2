import sqlite3, os
db = sqlite3.connect('churches_recovering.db')
c = db.cursor()
c.execute('PRAGMA integrity_check')
print('Integrity:', c.fetchone()[0])
for tbl in ['churches','church_sources','church_staff','org_links','org_officers','provenance_log','pss_schools','sources']:
    try:
        c.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        print(f'{tbl}: {c.fetchone()[0]:,}')
    except Exception as e:
        print(f'{tbl}: {e}')
db.close()

# Swap
if os.path.exists('churches.db'):
    os.rename('churches.db', 'churches.db.corrupt_backup')
os.rename('churches_recovering.db', 'churches.db')
print(f'\nchurches.db: {os.path.getsize("churches.db"):,} bytes')
print('Done!')

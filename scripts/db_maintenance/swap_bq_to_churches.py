"""Swap bq_churches into main churches table"""
import sqlite3, os, shutil
from datetime import datetime

DB = 'E:/grid/churches.db'

# Backup current DB
backup = f'E:/grid/churches_pre_bqswap_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
print(f'Backing up to {backup}...')
shutil.copy2(DB, backup)
print(f'Backup: {os.path.getsize(backup):,} bytes')

db = sqlite3.connect(DB, timeout=300)
c = db.cursor()

# Verify bq_churches
c.execute('SELECT COUNT(*) FROM bq_churches')
bq_count = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM churches')
old_count = c.fetchone()[0]
print(f'Current churches: {old_count:,}')
print(f'bq_churches: {bq_count:,}')

# Verify bq_churches integrity
c.execute('PRAGMA integrity_check')
print(f'Pre-swap integrity: {c.fetchone()[0]}')

# SWAP
print('Swapping tables...')
c.execute('DROP TABLE IF EXISTS churches_old')
c.execute('ALTER TABLE churches RENAME TO churches_old')
c.execute('ALTER TABLE bq_churches RENAME TO churches')
db.commit()

# Verify
c.execute('SELECT COUNT(*) FROM churches')
new_count = c.fetchone()[0]
c.execute('PRAGMA integrity_check')
print(f'Post-swap integrity: {c.fetchone()[0]}')
print(f'churches: {new_count:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
print(f'websites: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
print(f'emails: {c.fetchone()[0]:,}')

# Drop old table
c.execute('DROP TABLE IF EXISTS churches_old')
db.commit()
db.close()

# VACUUM to reclaim space
print('Vacuuming...')
db = sqlite3.connect(DB, timeout=300)
db.execute('VACUUM')
db.close()

size = os.path.getsize(DB)
print(f'\n=== DONE ===')
print(f'churches.db: {size:,} bytes ({size/1024/1024:.0f} MB)')
print(f'Restored: {new_count:,} churches ({new_count - old_count:,} more than before)')
print(f'Backup saved to: {backup}')

"""
Add website, email, phone columns to churches table
and populate from church_contacts.
"""
import sqlite3, time

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=120)
c = conn.cursor()

# Check which columns already exist
c.execute('PRAGMA table_info(churches)')
existing = {r[1] for r in c.fetchall()}

print(f'Existing churches columns: {len(existing)}')
print(f'  Has website: {"website" in existing}')
print(f'  Has email: {"email" in existing}')
print(f'  Has phone: {"phone" in existing}')
print()

# Add missing columns
for col in ['website', 'email', 'phone']:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} TEXT')
        print(f'  Added column: {col}')

conn.commit()

# Populate from church_contacts
print('\nPopulating from church_contacts...')
start = time.time()

# First pass: direct population
for col in ['website', 'email', 'phone']:
    c.execute(f"""
        UPDATE churches SET {col} = (
            SELECT {col} FROM church_contacts 
            WHERE church_contacts.church_id = churches.id 
            AND {col} IS NOT NULL AND {col} != ''
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM church_contacts 
            WHERE church_contacts.church_id = churches.id 
            AND {col} IS NOT NULL AND {col} != ''
        )
    """)
    print(f'  {col}: {c.rowcount:,} records populated')

conn.commit()

# Stats
c.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
print(f'\nFinal - Websites: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
print(f'Final - Emails: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''")
print(f'Final - Phones: {c.fetchone()[0]:,}')

elapsed = time.time() - start
print(f'\nDone in {elapsed:.1f}s')
conn.close()

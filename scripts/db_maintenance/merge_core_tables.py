"""Merge remaining tables from corrupt DB into recovering DB"""
import sqlite3, os

CORRUPT = 'churches.db.corrupt_20260615'  
RECOVERING = 'churches_recovering.db'
FINAL = 'churches.db'

src = sqlite3.connect(CORRUPT, timeout=300)
dst = sqlite3.connect(RECOVERING, timeout=300)
sc = src.cursor()
dc = dst.cursor()

# Drop indexes from source
sc.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'sqlite_autoindex_%'")
for r in sc.fetchall():
    try:
        sc.execute(f'DROP INDEX IF EXISTS "{r[0]}"')
    except:
        pass
src.commit()

# Skip government + ARDA (all easily re-downloadable/public)
SKIP = ['_acs_temp', 'census_zip_data', 'tract_acs_data', 'fcc_broadcast_data', 'irs_990_data', 
        'eac_eavs', 'election_results', 'fbi_ucr_crime',
        'arda_counts', 'arda_county_data', 'arda_denom_lookup', 'arda_denom_map',
        '_attendance_results', '_church_arena', '_county_denom_counts',
        'broadcast_coverage', 'broadcast_ministries', 'broadcast_transmitters',
        'enrichment_change_log']
sc.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'churches' ORDER BY name")
all_tables = [r[0] for r in sc.fetchall()]
tables = [t for t in all_tables if t not in SKIP]
print(f'Tables to copy ({len(tables)}): {tables}')
print(f'Skipped ({len(SKIP)}): {[t for t in all_tables if t in SKIP]}')

total_ok = 0
total_bad = 0

for tbl in tables:
    # Get columns via PRAGMA
    sc.execute(f'PRAGMA table_info("{tbl}")')
    cols = [(r[1], r[2]) for r in sc.fetchall()]
    if not cols:
        print(f'  {tbl}: no columns, skipping')
        continue
    col_names = [c[0] for c in cols]
    col_quoted = ', '.join(f'"{c}"' for c in col_names)
    ph = ', '.join(['?'] * len(cols))
    
    # Create in destination
    col_defs = ', '.join(f'"{c[0]}" {c[1]}' if c[1] else f'"{c[0]}"' for c in cols)
    try:
        dc.execute(f'CREATE TABLE IF NOT EXISTS "{tbl}" ({col_defs})')
    except:
        pass
    dst.commit()
    
    # Get count
    try:
        sc.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        total = sc.fetchone()[0]
    except:
        print(f'  {tbl}: count FAIL, skipping')
        continue
    
    added = 0
    failed = 0
    offset = 0
    
    while True:
        try:
            sc.execute(f'SELECT {col_quoted} FROM "{tbl}" LIMIT 500 OFFSET {offset}')
            rows = sc.fetchall()
        except:
            failed += 500
            offset += 500
            continue
        
        if not rows:
            break
        
        for row in rows:
            try:
                dc.execute(f'INSERT OR IGNORE INTO "{tbl}" ({col_quoted}) VALUES ({ph})', row)
                added += 1
            except:
                failed += 1
        dst.commit()
        offset += len(rows)
    
    pct = f' (lost {failed/total*100:.1f}%)' if total > 0 and failed > 0 else ''
    print(f'  {tbl}: {added:,}/{total:,}{pct}')
    total_ok += added
    total_bad += failed

# Final verify
dc.execute('PRAGMA integrity_check')
print(f'\nFinal integrity: {dc.fetchone()[0]}')
dc.execute('SELECT COUNT(*) FROM churches')
print(f'churches: {dc.fetchone()[0]:,}')

for tbl in tables:
    try:
        dc.execute(f'SELECT COUNT(*) FROM "{tbl}"')
        print(f'  {tbl}: {dc.fetchone()[0]:,}')
    except:
        pass

src.close()
dst.close()

# Replace corrupt DB with recovered DB
print('\n=== Finalizing ===')
if os.path.exists(FINAL):
    os.rename(FINAL, 'churches.db.corrupt_backup')
os.rename(RECOVERING, FINAL)
print(f'{FINAL}: {os.path.getsize(FINAL):,} bytes')

db = sqlite3.connect(FINAL)
c = db.cursor()
c.execute('SELECT COUNT(*) FROM churches')
print(f'churches: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
print(f'websites: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
print(f'emails: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''")
print(f'phones: {c.fetchone()[0]:,}')
c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''")
print(f'denominated: {c.fetchone()[0]:,}')
try:
    c.execute('SELECT SUM(estimated_attendance) FROM churches')
    print(f'attendance total: {int(c.fetchone()[0] or 0):,}')
except: pass
c.execute('SELECT COUNT(*) FROM church_staff')
print(f'church_staff: {c.fetchone()[0]:,}')
c.execute('SELECT COUNT(*) FROM org_links')
print(f'org_links: {c.fetchone()[0]:,}')
db.close()
print('\nDone!')

"""Audit what churches were lost in the recovery"""
import sqlite3

# The finalized churches.db on D: has 183K rows from 385K corrupt original
# The corrupt backup still has all 385K (some unreachable)

RECOVERED = 'churches.db'
GCS_BACKUP = 'churches_gcs_backup.db'
CORRUPT = 'churches.db.corrupt_20260615'

rc = sqlite3.connect(RECOVERED)

# Try GCS backup first (should be clean, from June 14)
print('=== GCS BACKUP (June 14) ===')
try:
    gc = sqlite3.connect(GCS_BACKUP)
    gc_cur = gc.cursor()
    gc_cur.execute('PRAGMA integrity_check')
    print(f'Integrity: {gc_cur.fetchone()[0]}')
    gc_cur.execute('SELECT COUNT(*) FROM churches')
    gcs_total = gc_cur.fetchone()[0]
    print(f'Total churches: {gcs_total:,}')
    gc_cur.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
    print(f'Websites: {gc_cur.fetchone()[0]:,}')
    gc_cur.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
    print(f'Emails: {gc_cur.fetchone()[0]:,}')
    gc_cur.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''")
    print(f'Denominated: {gc_cur.fetchone()[0]:,}')
    gc_cur.execute("SELECT SUM(estimated_attendance) FROM churches")
    print(f'Attendance total: {int(gc_cur.fetchone()[0] or 0):,}')
    
    # Denom distribution in GCS
    print()
    print('=== TOP 15 DENOMINATIONS (GCS backup) ===')
    gc_cur.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != '' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15")
    for r in gc_cur.fetchall():
        print(f'  {r[0][:45]:<45} {r[1]:>8,}')
    
    # Other tables
    print()
    print('=== OTHER TABLES ===')
    for tbl in ['church_sources','church_staff','org_links','provenance_log','pss_schools','arda_counts','arda_county_data','census_zip_data']:
        try:
            gc_cur.execute(f'SELECT COUNT(*) FROM "{tbl}"')
            print(f'  {tbl}: {gc_cur.fetchone()[0]:,}')
        except:
            pass
    
    gc.close()
except Exception as e:
    print(f'GCS backup: {e}')

# Compare with recovered
print()
print('=== RECOVERED (from repair today) ===')
rc_cur = rc.cursor()
rc_cur.execute('SELECT COUNT(*) FROM churches')
print(f'Total churches: {rc_cur.fetchone()[0]:,}')
rc_cur.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''")
print(f'Websites: {rc_cur.fetchone()[0]:,}')
rc_cur.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''")
print(f'Emails: {rc_cur.fetchone()[0]:,}')
rc_cur.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''")
print(f'Denominated: {rc_cur.fetchone()[0]:,}')

if gcs_total:
    print()
    print(f'=== CAN RECOVER ADDITIONAL {gcs_total - rc_cur.fetchone()[0]:,} FROM GCS ===' if False else '')

rc.close()

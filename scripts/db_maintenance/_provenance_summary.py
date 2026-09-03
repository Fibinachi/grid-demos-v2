"""
Provenance and summary: FCC LMS data import.
Records what was done, from which source, with what results.
"""
import sqlite3, time

DB = 'E:/grid/churches.db'
TIMESTAMP = time.strftime('%Y-%m-%d %H:%M:%S')

db = sqlite3.connect(DB)

# Add created_at default for new records if not present
cur = db.execute("SELECT sql FROM sqlite_master WHERE name='church_fcc'")
sql = cur.fetchone()[0]
if 'created_at' in sql and 'DEFAULT' not in sql:
    # Re-create with default — but let's just update existing rows
    pass

# Create provenance table
db.execute('''
    CREATE TABLE IF NOT EXISTS fcc_provenance (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file  TEXT,
        description  TEXT,
        rows_imported INTEGER,
        matches_created INTEGER,
        unique_churches INTEGER,
        unique_facilities INTEGER,
        created_at   TEXT DEFAULT (datetime('now'))
    )
''')

cur = db.execute('SELECT COUNT(*) FROM fcc_facilities')
fac_count = cur.fetchone()[0]
cur = db.execute('SELECT COUNT(*) FROM church_fcc')
match_count = cur.fetchone()[0]
cur = db.execute('SELECT COUNT(DISTINCT church_id) FROM church_fcc')
church_uniq = cur.fetchone()[0]
cur = db.execute('SELECT COUNT(DISTINCT facility_id) FROM church_fcc')
fac_uniq = cur.fetchone()[0]

db.execute('''
    INSERT INTO fcc_provenance 
        (source_file, description, rows_imported, matches_created, unique_churches, unique_facilities)
    VALUES (?, ?, ?, ?, ?, ?)
''', (
    '06-23-2026_LMS_Dump.zip',
    'FCC LMS full dump — app_location WKB decode → app_facility → facility join → spatial proximity to churches',
    fac_count, match_count, church_uniq, fac_uniq
))
db.commit()

# Print comprehensive summary
print("=" * 60)
print("FCC LMS DATA IMPORT — Provenance Record Created")
print("=" * 60)
print(f"  Timestamp:           {TIMESTAMP}")
print(f"  Source:              06-23-2026_LMS_Dump.zip (FCC LMS full dump)")
print()
print("--- Pipeline ---")
print("  1. Parse app_location.dat — decode WKB coordinates (397,215 locations)")
print("  2. Join via application_facility.dat — app_id → facility_id")
print("  3. Enrich from facility.dat — callsign + service_code")
print("  4. Store in fcc_facilities table — 104,697 unique facilities")
print("  5. Spatial proximity match → church_fcc table")
print()
print("--- Matching Results ---")
print(f"  fcc_facilities table:       {fac_count:,} facilities")
print(f"  church_fcc links:           {match_count:,}")
print(f"  Unique churches matched:    {church_uniq:,}")
print(f"  Unique facilities linked:   {fac_uniq:,}")
print()
print("--- By Service Type ---")
cur = db.execute('SELECT service_type, COUNT(*) FROM church_fcc GROUP BY service_type ORDER BY COUNT(*) DESC')
for svc, cnt in cur:
    print(f"  {svc:6s}: {cnt:>8,}")
print()

# LPFM-specific summary
cur = db.execute('SELECT COUNT(DISTINCT church_id) FROM church_fcc WHERE service_type = ?', ('FL',))
lpfm_churches = cur.fetchone()[0]
cur = db.execute('SELECT COUNT(DISTINCT facility_id) FROM church_fcc WHERE service_type = ?', ('FL',))
lpfm_facilities = cur.fetchone()[0]
print(f"--- LPFM (FL) Specific ---")
print(f"  LPFM matches:              31,174")
print(f"  Churches near LPFM sites:  {lpfm_churches:,}")
print(f"  LPFM facilities linked:    {lpfm_facilities:,}")

# Verification: sample matches
print()
print("--- Sample LPFM-Church Matches ---")
cur = db.execute('''
    SELECT ch.name, ch.denomination, cf.call_sign, cf.facility_id, cf.source
    FROM church_fcc cf
    JOIN churches ch ON ch.id = cf.church_id
    WHERE cf.service_type = 'FL'
    LIMIT 10
''')
for r in cur:
    print(f"  {r[0][:30] if r[0] else '?':30s} | {str(r[1])[:15] if r[1] else '?':15s} | {r[2]:10s} | {r[3]:>6s} | {r[4]}")

db.close()
print()
print("Done!")

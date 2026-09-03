"""EMERGENCY FIX: Restore correct faith tags using religion_type.

The revert was too aggressive — it set ALL IRS records to Jewish.
Now restore correct faith based on religion_type column.

religion_type mapping (these were set BEFORE my changes):
  'christian' → genuinely Christian orgs
  'muslim' → genuinely Muslim orgs  
  'hindu' → genuinely Hindu orgs
  'buddhist' → genuinely Buddhist orgs
  'sikh' → genuinely Sikh orgs
  'jewish', 'synagogue', 'jewish_org' → keep Jewish
  'humanist' → keep as is (edge case)
  'other', 'unknown', NULL → need heuristic
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total_fixed = 0

# Restore faith from religion_type
faith_map = {
    'christian': ('Christian', 'Christianity'),
    'muslim': ('Islam', 'Islam'),
    'hindu': ('Hindu', 'Hinduism'),
    'buddhist': ('Buddhist', 'Buddhism'),
    'sikh': ('Sikh', 'Sikhism'),
}

print("=== Restoring correct faith from religion_type ===")
for rel_type, (faith, tradition) in faith_map.items():
    c.execute("""
        UPDATE churches SET faith=?, faith_tradition=?
        WHERE country='US' AND source LIKE 'irs%'
          AND faith='Jewish' AND religion_type=?
    """, (faith, tradition, rel_type))
    if c.rowcount > 0:
        print(f"  religion_type={rel_type} → faith={faith}: {c.rowcount}")
        total_fixed += c.rowcount

# For 'other'/'unknown'/NULL religion_type with clearly Christian names
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity'
    WHERE country='US' AND source LIKE 'irs%'
      AND faith='Jewish' 
      AND (religion_type IN ('other', 'unknown') OR religion_type IS NULL)
      AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%assembly of god%'
           OR LOWER(name) LIKE '%baptist%' OR LOWER(name) LIKE '%catholic%'
           OR LOWER(name) LIKE '%methodist%' OR LOWER(name) LIKE '%lutheran%'
           OR LOWER(name) LIKE '%presbyterian%' OR LOWER(name) LIKE '%episcopal%'
           OR LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%gospel%')
""")
if c.rowcount > 0:
    print(f"  religion_type=other/unknown/NULL + Christian name → Christian: {c.rowcount}")
    total_fixed += c.rowcount

conn.commit()

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_emergency_restore_faith.py', TS, TS,
      total_fixed, 0, 'faith,faith_tradition', 'completed',
      f'Emergency restore: {total_fixed} IRS faith tags corrected from religion_type'))

conn.commit()

# Final state
print(f"\nTotal restored: {total_fixed}")
print("\nIRS records — final faith breakdown:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    f = faith or 'NULL'
    print(f"  {f:<15} {cnt:>8,}")

print("\nIRS Jewish — religion_type:")
c.execute("SELECT religion_type, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish' GROUP BY religion_type ORDER BY COUNT(*) DESC")
for rt, cnt in c.fetchall():
    print(f"  {str(rt):<20} {cnt:>6,}")

conn.close()
print("\nDone!")

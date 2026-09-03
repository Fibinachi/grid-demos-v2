"""Verify provenance logging from the NA scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# 1. Check provenance_log
print("=== provenance_log ===")
c.execute("SELECT id, source, script_name, started_at, completed_at, churches_updated, churches_inserted, status, notes FROM provenance_log WHERE script_name='scan_na_jewish_deepseek'")
for r in c.fetchall():
    print(f"  id={r[0]} source={r[1]} script={r[2]}")
    print(f"  started={r[3]} completed={r[4]}")
    print(f"  updated={r[5]} inserted={r[6]} status={r[7]}")
    print(f"  notes={r[8]}")

# 2. Check enrichment_change_log for recent entries
print("\n=== Recent enrichment_change_log entries (last 5) ===")
c.execute("SELECT church_id, field_name, old_value, new_value, change_source, changed_at FROM enrichment_change_log ORDER BY id DESC LIMIT 5")
for r in c.fetchall():
    print(f"  church={r[0]} field={r[1]:20s} old={str(r[2] or '')[:30]:30s} new={str(r[3] or '')[:30]:30s} source={r[4]:20s} at={r[5]}")

# 3. Count deepseek entries in enrichment_change_log
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_na_scan'")
count = c.fetchone()[0]
print(f"\nTotal deepseek_na_scan entries in enrichment_change_log: {count:,}")

# 4. Show distribution by field
c.execute("SELECT field_name, COUNT(*) FROM enrichment_change_log WHERE change_source='deepseek_na_scan' GROUP BY field_name ORDER BY COUNT(*) DESC")
print("\nBy field:")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>7,}")

# 5. Check a specific church change
c.execute("SELECT church_id, field_name, old_value, new_value, change_source FROM enrichment_change_log WHERE change_source='deepseek_na_scan' ORDER BY id DESC LIMIT 20")
print("\nSample of 20 deepseek changes:")
for r in c.fetchall():
    print(f"  church={r[0]} field={r[1]:20s} old={str(r[2] or '')[:30]:30s} new={str(r[3] or '')[:30]:30s}")

# 6. Fix the 28 NULL landmark_type entries
print("\n\n=== Fixing remaining NULL landmark_type entries ===")
c.execute("""
    SELECT id, name FROM churches WHERE faith='Judaism' AND country='Canada'
    AND (landmark_type IS NULL OR landmark_type = '')
    ORDER BY name
""")
null_entries = c.fetchall()
print(f"Fixing {len(null_entries)} entries with NULL landmark_type")

for row in null_entries:
    c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=?", (row[0],))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'landmark_type', NULL, 'synagogue', 'deepseek_na_scan_fix')",
              (row[0],))

conn.commit()
print(f"Fixed {len(null_entries)} entries -> synagogue")

# 7. Also fix the MA/MI entries that should be Ontario
c.execute("UPDATE churches SET state='Ontario' WHERE faith='Judaism' AND country='Canada' AND state IN ('MA','MI')")
fixed = c.rowcount
if fixed:
    for row in c.execute("SELECT id FROM churches WHERE faith='Judaism' AND country='Canada' AND state IN ('MA','MI')").fetchall():
        pass  # already updated above
    print(f"Fixed {fixed} entries: MA/MI -> Ontario (log skipped, already updated)")

# Actually the update already happened, let me log it properly
c.execute("SELECT id, state FROM churches WHERE faith='Judaism' AND country='Canada' AND state IN ('MA','MI')")
for row in c.fetchall():
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'state', ?, 'Ontario', 'deepseek_na_scan_fix')",
              (row[0], row[1]))
conn.commit()
print(f"Logged {c.rowcount} state fixes to enrichment_change_log")

# Final check
c.execute("""
    SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country='Canada'
    AND (landmark_type IS NULL OR landmark_type = '')
""")
remaining_null = c.fetchone()[0]
print(f"\nRemaining NULL landmark_type in Canada: {remaining_null}")

c.execute("SELECT state, COUNT(*) FROM churches WHERE faith='Judaism' AND country='Canada' GROUP BY state ORDER BY COUNT(*) DESC")
print("\nFinal Canada province distribution:")
for r in c.fetchall():
    print(f"  {r[0]:30s} {r[1]:>5,}")

conn.close()
print("\nDone!")

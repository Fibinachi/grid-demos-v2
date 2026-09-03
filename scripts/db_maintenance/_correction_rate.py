"""Calculate correction rate from deepseek scans."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
israel = c.fetchone()[0]
print(f"Total Judaism worldwide: {total:,}")
print(f"  Israel (not scanned): {israel:,}")
print(f"  Scanned regions: {total - israel:,}")

# Count enrichment log entries by source
c.execute("""
    SELECT change_source, 
           COUNT(*) as changes,
           COUNT(DISTINCT church_id) as churches,
           SUM(CASE WHEN field_name='faith' THEN 1 ELSE 0 END) as faith_changes
    FROM enrichment_change_log 
    WHERE change_source LIKE 'deepseek%'
    GROUP BY change_source
    ORDER BY change_source
""")
rows = c.fetchall()

total_changes = 0
total_churches = set()
total_faith_moved = 0

print(f"\n=== DeepSeek scan provenance ===")
for r in rows:
    source, changes, churches, faith_changes = r
    total_changes += changes
    total_faith_moved += faith_changes
    print(f"  {source:30s} {changes:>6,} changes in {churches:>5,} churches ({faith_changes} faith moved)")

# Correction rate
scanned = total - israel
faith_rate = total_faith_moved / scanned * 100
total_correction_rate = total_changes / scanned * 100

print(f"\n=== Correction Rate ===")
print(f"Entries scanned (ex-Israel): {scanned:,}")
print(f"Faith corrections (moved out of Judaism): {total_faith_moved:,} ({faith_rate:.2f}%)")
print(f"Total field corrections (faith+trad+type+state): {total_changes:,} ({total_correction_rate:.2f}%)")
print(f"\nInterpretation:")
print(f"  - {total_faith_moved:,} entries ({faith_rate:.2f}%) were completely wrong faith (non-Jewish)")
if total_changes > total_faith_moved:
    print(f"  - {total_changes - total_faith_moved:,} additional field corrections (tradition/type/state)")
print(f"  - Overall {total_correction_rate:.1f}% of entries needed *some* correction")

conn.close()

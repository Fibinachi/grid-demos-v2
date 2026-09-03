"""Final summary of all DeepSeek Jewish scans."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il = c.fetchone()[0]
ex_il = total - il

print(f"Worldwide Judaism: {total:,}")
print(f"  Israel: {il:,}")
print(f"  Ex-Israel: {ex_il:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
print(f"Problematic entries: {c.fetchone()[0]}")

# Total provenance entries
c.execute("SELECT change_source, COUNT(*) FROM enrichment_change_log WHERE change_source LIKE 'deepseek%' GROUP BY change_source ORDER BY change_source")
print(f"\nDeepSeek provenance:")
total_changes = 0
for r in c.fetchall():
    total_changes += r[1]
    print(f"  {r[0]:35s} {r[1]:>6,}")
print(f"  {'TOTAL':35s} {total_changes:>6,}")

c.execute("SELECT COUNT(DISTINCT church_id) FROM enrichment_change_log WHERE change_source LIKE 'deepseek%'")
print(f"\nUnique churches modified: {c.fetchone()[0]:,}")

# Faith corrections
c.execute("SELECT COUNT(*) FROM enrichment_change_log WHERE change_source LIKE 'deepseek%' AND field_name='faith'")
faith_moves = c.fetchone()[0]
print(f"Faith moved out of Judaism: {faith_moves}")

conn.close()

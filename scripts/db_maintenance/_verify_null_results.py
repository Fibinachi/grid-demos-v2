"""Verify NULL faith DeepSeek classification results."""
import sqlite3

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

print("=== NULL faith → Other: sample (20) ===")
for row in c.execute("""SELECT id, name, city, country, tradition, landmark_type 
    FROM churches WHERE id IN (
        SELECT church_id FROM enrichment_change_log WHERE change_source='deepseek_null_faith_scan'
    ) AND faith='Other' LIMIT 20"""):
    print(f"  {row[0]:>10} | {str(row[1] or '')[:55]:55s} | {str(row[2] or '')[:20]:20s} | {str(row[3] or '')[:5]:5s} | {str(row[4] or '')[:20]:20s} | {str(row[5] or '')[:15]:15s}")

print()
print("=== NULL faith → Christian: ALL ===")
for row in c.execute("""SELECT id, name, city, country, tradition, landmark_type 
    FROM churches WHERE id IN (
        SELECT church_id FROM enrichment_change_log WHERE change_source='deepseek_null_faith_scan'
    ) AND faith='Christian'"""):
    print(f"  {row[0]:>10} | {str(row[1] or '')[:55]:55s} | {str(row[2] or '')[:20]:20s} | {str(row[3] or '')[:5]:5s} | {str(row[4] or '')[:20]:20s} | {str(row[5] or '')[:15]:15s}")

print()
print("=== NULL faith → Others (Hindu, Islam, etc.) ===")
for row in c.execute("""SELECT faith, COUNT(*) FROM churches WHERE id IN (
        SELECT church_id FROM enrichment_change_log WHERE change_source='deepseek_null_faith_scan'
    ) AND faith NOT IN ('Christian','Other') GROUP BY faith ORDER BY COUNT(*) DESC"""):
    print(f"  {row[0]:15s} {row[1]:>6}")

print()
print("=== NULL faith → Other: country breakdown (top 10) ===")
for row in c.execute("""SELECT country, COUNT(*) FROM churches WHERE id IN (
        SELECT church_id FROM enrichment_change_log WHERE change_source='deepseek_null_faith_scan'
    ) AND faith='Other' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10"""):
    print(f"  {str(row[0] or 'NULL'):8s} {row[1]:>6}")

conn.close()

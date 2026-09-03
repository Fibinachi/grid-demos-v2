"""Verify all classifier results."""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")

print("=== OVERVIEW ===")
total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
null_faith = db.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
print(f"{'Total churches':35s} {total:>10,}")
print(f"{'Null faith (remaining)':35s} {null_faith:>10,}")
print()

# Faith breakdown
print("=== FAITH BREAKDOWN ===")
rows = db.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC").fetchall()
for r in rows:
    print(f"  {r[0]:30s} {r[1]:>10,}")

print()
print("=== MUSLIM DOCTRINAL BREAKDOWN ===")
muslim = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam'").fetchone()[0]
affiliated = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND muslim_affiliation IS NOT NULL AND muslim_affiliation != ''").fetchone()[0]
print(f"{'Total Islam':35s} {muslim:>10,}")
print(f"{'With doctrinal affiliation':35s} {affiliated:>10,}")
print(f"{'Unclassified doctrinal':35s} {muslim - affiliated:>10,}")
print()
rows = db.execute("""
    SELECT muslim_affiliation, COUNT(*) 
    FROM churches WHERE faith='Islam' AND muslim_affiliation IS NOT NULL AND muslim_affiliation != '' 
    GROUP BY muslim_affiliation ORDER BY COUNT(*) DESC
""").fetchall()
for r in rows:
    print(f"  {r[0]:30s} {r[1]:>10,}")

print()
print("=== REMAINING NULL FAITH BY COUNTRY (top 15) ===")
rows = db.execute("""
    SELECT country, COUNT(*) 
    FROM churches WHERE faith IS NULL OR faith = '' 
    GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15
""").fetchall()
for r in rows:
    print(f"  {r[0]:5s} {r[1]:>10,}")

print()
print("=== REMAINING NULL FAITH BY SOURCE (top 5) ===")
rows = db.execute("""
    SELECT source, COUNT(*) 
    FROM churches WHERE faith IS NULL OR faith = '' 
    GROUP BY source ORDER BY COUNT(*) DESC LIMIT 5
""").fetchall()
for r in rows:
    print(f"  {r[0]:30s} {r[1]:>10,}")

print()
print("=== SAMPLE REMAINING NULL FAITH (10 random) ===")
rows = db.execute("""
    SELECT name, country, landmark_type, source
    FROM churches WHERE faith IS NULL OR faith = ''
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  {str(r[0]):50s}  {str(r[1]):5s}  {str(r[2]):20s}  {str(r[3]):25s}")

print()
print("=== PROVENANCE LOG (recent entries) ===")
rows = db.execute("""
    SELECT script_name, churches_updated, notes, completed_at
    FROM provenance_log
    ORDER BY completed_at DESC
    LIMIT 5
""").fetchall()
for r in rows:
    print(f"  {str(r[0]):30s}  {r[1]:>8,}  {str(r[2]):60s}  {str(r[3])}")

db.close()

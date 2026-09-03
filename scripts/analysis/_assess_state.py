"""Assess current state of NHL provenance and Muslim classification."""
import sqlite3, sys
sys.path.insert(0, ".")

conn = sqlite3.connect("churches.db")
c = conn.cursor()

print("=== NHL PROVENANCE ===")
c.execute("SELECT id, source, script_name, status, churches_updated, churches_inserted, started_at, completed_at, records_attempted FROM provenance_log WHERE source LIKE '%nhl%' OR source LIKE '%wikipedia%' OR source = 'fix_nhl_missing' ORDER BY id")
rows = c.fetchall()
for r in rows:
    print(f"  id={r[0]} | src={r[1]:25s} | script={str(r[2] or ''):25s} | {r[3]} | updated={r[4]} inserted={r[5]} | attempted={r[8]}")

c.execute("SELECT COUNT(*) FROM churches WHERE heritage_status LIKE '%National Historic Landmark%'")
total_nhl = c.fetchone()[0]
print(f"\nTotal churches with NHL flag: {total_nhl}")

print("\n\n=== MUSLIM CLASSIFICATION STATE ===")
# Check faith counts
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith = 'Islam' OR faith LIKE 'Muslim%' GROUP BY faith")
for r in c.fetchall():
    print(f"  faith={r[0]}: {r[1]:,}")

c.execute("SELECT faith, tradition, COUNT(*) FROM churches WHERE faith='Islam' GROUP BY tradition ORDER BY COUNT(*) DESC")
rows = c.fetchall()
total_islam = sum(r[2] for r in rows)
print(f"\n  Total Islam: {total_islam:,}")
for r in rows:
    pct = r[2]/total_islam*100 if total_islam else 0
    print(f"    {str(r[0] or 'NULL'):15s} / {str(r[1] or 'unclassified'):25s}: {r[2]:>8,} ({pct:5.1f}%)")

# Check unclassified Islam 
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (tradition IS NULL OR tradition = '' OR taxonomy_id IS NULL)")
unclass = c.fetchone()[0]
print(f"\n  Islam with NULL tradition: {unclass:,}")

# Check geo-prior map
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''")
classified = c.fetchone()[0]
print(f"  Islam with tradition set: {classified:,}")

# What's the taxonomy for Islam?
print("\n\n=== ISLAM TAXONOMY TREE ===")
c.execute("SELECT id, parent_id, name FROM taxonomy WHERE parent_id = 4 OR id = 4 ORDER BY id")
for r in c.fetchall():
    print(f"  id={r[0]:>5d} | parent={str(r[1] or ''):>5s} | {r[2]}")

conn.close()

"""Check diocese mapping and pss_schools merge connections"""
import sqlite3

db = sqlite3.connect("E:\\grid\\churches.db")
db.row_factory = sqlite3.Row
cur = db.cursor()

# Check county_diocese_map
cur.execute("PRAGMA table_info(county_diocese_map)")
cols = cur.fetchall()
print("=== county_diocese_map COLUMNS ===")
for c in cols:
    print(f"  {c[1]:30s} {c[2]:20s}")
cur.execute("SELECT COUNT(*) FROM county_diocese_map")
print(f"Count: {cur.fetchone()[0]}")
cur.execute("SELECT * FROM county_diocese_map LIMIT 5")
for r in cur.fetchall():
    print(dict(r))
print()

# Check sources table
cur.execute("PRAGMA table_info(sources)")
cols = cur.fetchall()
print("=== sources COLUMNS ===")
for c in cols:
    print(f"  {c[1]:30s} {c[2]:20s}")
cur.execute("SELECT * FROM sources")
for r in cur.fetchall():
    print(dict(r))
print()

# pss_schools diocese codes, first 20
cur.execute("SELECT DISTINCT diocese FROM pss_schools WHERE diocese IS NOT NULL AND diocese != '' ORDER BY diocese LIMIT 20")
print("First 20 pss_schools diocese codes:")
for r in cur.fetchall():
    print(f"  {r[0]}")

# merge_target_id
cur.execute("SELECT COUNT(*) FROM pss_schools WHERE merge_target_id IS NOT NULL")
mcnt = cur.fetchone()[0]
print(f"\npss_schools with merge_target_id: {mcnt}")

cur.execute("SELECT COUNT(*) FROM pss_schools ps JOIN churches c ON ps.merge_target_id = c.id")
mcnt2 = cur.fetchone()[0]
print(f"pss_schools merge_target_id matching churches: {mcnt2}")

# Show unmatched merge targets
cur.execute("""
    SELECT ps.merge_target_id, ps.pinst
    FROM pss_schools ps
    LEFT JOIN churches c ON ps.merge_target_id = c.id
    WHERE c.id IS NULL AND ps.merge_target_id IS NOT NULL
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  Unmatched merge_target {r[0]}: {r[1][:50]}")

# Source values
cur.execute("SELECT DISTINCT source FROM churches WHERE source LIKE '%pss%' OR source LIKE '%school%'")
for r in cur.fetchall():
    print(f"Source: {r[0]}")

# Check the provenance_log for schools
cur.execute("SELECT COUNT(*) FROM provenance_log WHERE details LIKE '%school%' OR details LIKE '%pss%'")
print(f"School-related provenance entries: {cur.fetchone()[0]}")

# Check if church_sources has entries for pss
cur.execute("SELECT COUNT(*) FROM church_sources WHERE source_name LIKE '%pss%' OR source_name LIKE '%school%'")
print(f"Church_sources with pss/school: {cur.fetchone()[0]}")

db.close()

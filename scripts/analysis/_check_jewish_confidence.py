"""Check Jewish confidence score coverage and movement distribution."""
import sqlite3

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
print(f"Total Judaism: {total:,}")

print("\nTradition distribution:")
c.execute("""SELECT tradition, COUNT(*) 
FROM churches WHERE faith='Judaism' 
GROUP BY tradition ORDER BY COUNT(*) DESC LIMIT 20""")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# IRS check
print("\n--- IRS-sourced Jewish entries ---")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND source LIKE '%irs%'")
irs_total = c.fetchone()[0]
print(f"Total IRS-sourced: {irs_total:,}")

c.execute("""SELECT denomination, COUNT(*) FROM churches 
WHERE faith='Judaism' AND source LIKE '%irs%' 
GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15""")
print("\nIRS denom distribution:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

c.execute("""SELECT landmark_type, COUNT(*) FROM churches 
WHERE faith='Judaism' AND source LIKE '%irs%' 
GROUP BY landmark_type ORDER BY COUNT(*) DESC LIMIT 15""")
print("\nIRS landmark_type distribution:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# Generic confidence_score check
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND confidence_score IS NOT NULL")
print(f"\nWith generic confidence_score: {c.fetchone()[0]:,}")

c.execute("""SELECT confidence_score, COUNT(*) FROM churches 
WHERE faith='Judaism' AND confidence_score IS NOT NULL 
GROUP BY confidence_score ORDER BY COUNT(*) DESC""")
print("Confidence score values:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# Muslim columns pattern (for reference)
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND muslim_confidence IS NOT NULL")
print(f"\nMuslim confidence coverage: {c.fetchone()[0]:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam'")
print(f"Total Islam: {c.fetchone()[0]:,}")

# Check what columns actually exist that have 'jewish' in the name anywhere
c.execute("PRAGMA table_info(churches)")
cols = [r[1] for r in c.fetchall()]
jewish_cols = [c for c in cols if 'jewish' in c.lower() or 'judais' in c.lower()]
print(f"\nJewish-related columns in churches table: {jewish_cols if jewish_cols else 'NONE'}")

# Check if there's a church_enrichment table
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%jewish%'")
jewish_tables = [r[0] for r in c.fetchall()]
print(f"Jewish-related tables: {jewish_tables if jewish_tables else 'NONE'}")

# IRS verification checks
print("\n--- IRS Verification ---")
checks = [
    ("denom populated", "source LIKE '%irs%' AND denomination IS NOT NULL AND denomination != ''"),
    ("Christian landmark_type", "source LIKE '%irs%' AND landmark_type IN ('church','cathedral','chapel','basilica','parish','monastery','convent','rectory','abbey')"),
    ("CHURCH in name", "source LIKE '%irs%' AND name LIKE '%CHURCH%'"),
    ("MINISTRY in name", "source LIKE '%irs%' AND name LIKE '%MINISTR%'"),
    ("FELLOWSHIP in name", "source LIKE '%irs%' AND name LIKE '%FELLOWSHIP%'"),
]
for label, condition in checks:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND {condition}")
    print(f"  {label}: {c.fetchone()[0]:,}")

# Check IRS entries that are NOT Jewish (possibly fixed by cleanup scripts)
c.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%irs%' AND faith != 'Judaism' AND landmark_type IN ('synagogue','chabad_house','yeshiva','mikveh','kollel')")
print(f"\n  Non-Jewish IRS with Jewish landmark_type: {c.fetchone()[0]:,}")

# How many entries in enrichment_change_log touched by IRS fix scripts
c.execute("SELECT change_source, COUNT(*) FROM enrichment_change_log WHERE change_source LIKE '%irs%jewish%' OR change_source LIKE '%jewish%irs%' GROUP BY change_source")
print("\nIRS Jewish fix enrichment log entries:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

# DeepSeek coverage of Jewish entries
c.execute("SELECT COUNT(DISTINCT church_id) FROM enrichment_change_log WHERE change_source LIKE 'deepseek%'")
print(f"\nChurches touched by any DeepSeek scan: {c.fetchone()[0]:,}")

c.execute("""SELECT COUNT(DISTINCT ecl.church_id) FROM enrichment_change_log ecl 
JOIN churches ch ON ecl.church_id = ch.id 
WHERE ecl.change_source LIKE 'deepseek%' AND ch.faith='Judaism'""")
print(f"  Of which are Judaism: {c.fetchone()[0]:,}")

conn.close()

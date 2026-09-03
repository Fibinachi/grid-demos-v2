"""Audit current Christian data state before denomination tagging."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

print("=== TOTAL CHRISTIAN RECORDS ===")
c = db.execute('SELECT COUNT(*) FROM churches WHERE faith = ?', ('Christian',))
print(f"  {c.fetchone()[0]:,}")

print("\n=== TOP 80 CHRISTIAN DENOMINATIONS ===")
c = db.execute("""
    SELECT COALESCE(denomination, 'NULL') as denom, COUNT(*) as cnt 
    FROM churches WHERE faith = 'Christian' 
    GROUP BY denom ORDER BY cnt DESC LIMIT 80
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== NULL/EMPTY DENOMINATION COUNT ===")
c = db.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Christian' AND (denomination IS NULL OR denomination = '')")
print(f"  {c.fetchone()[0]:,}")

print("\n=== FAITH_TRADITION DISTRIBUTION ===")
c = db.execute("""
    SELECT COALESCE(faith_tradition, 'NULL') as ft, COUNT(*) as cnt 
    FROM churches WHERE faith = 'Christian' 
    GROUP BY ft ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== SOURCE DISTRIBUTION ===")
c = db.execute("""
    SELECT source, COUNT(*) as cnt 
    FROM churches WHERE faith = 'Christian' 
    GROUP BY source ORDER BY cnt DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

print("\n=== DENOMINATION COUNTS BY SIZE TIER ===")
c = db.execute("""
    SELECT 
        CASE 
            WHEN cnt >= 100000 THEN '100K+'
            WHEN cnt >= 10000 THEN '10K-99K'
            WHEN cnt >= 1000 THEN '1K-9K'
            WHEN cnt >= 100 THEN '100-999'
            ELSE '1-99'
        END as tier,
        COUNT(*) as num_groups,
        SUM(cnt) as total_records
    FROM (
        SELECT COALESCE(denomination, 'NULL') as denom, COUNT(*) as cnt 
        FROM churches WHERE faith = 'Christian' 
        GROUP BY denom
    )
    GROUP BY tier ORDER BY MIN(cnt) DESC
""")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]} groups, {row[2]:,} records")

print("\n=== EXISTING DENOM CLASSIFICATION SCRIPTS ===")
import os, glob
scripts = glob.glob('_classify_*.py')
for s in sorted(scripts):
    print(f"  {s}")

db.close()

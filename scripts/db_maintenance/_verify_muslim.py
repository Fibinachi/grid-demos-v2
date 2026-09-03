"""Verify Muslim classification results."""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam'").fetchone()[0]
aff = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND muslim_affiliation IS NOT NULL AND muslim_affiliation != ''").fetchone()[0]
print(f'Islam total: {total:,}')
print(f'Islam with muslim_affiliation: {aff:,}')
print(f'Islam without: {total - aff:,}')

print('\nDoctrinal breakdown:')
report = c.execute("""
    SELECT muslim_affiliation, COUNT(*) as cnt, ROUND(AVG(muslim_confidence), 3) as avg_conf
    FROM churches WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    GROUP BY muslim_affiliation ORDER BY cnt DESC
""").fetchall()
for aff, cnt, conf in report:
    print(f'  {aff}: {cnt:,} (avg conf={conf})')

print(f'\nTotal classified: {sum(r[1] for r in report):,}')

print('\nSource breakdown:')
c.execute("""
    SELECT muslim_classification_source, COUNT(*)
    FROM churches WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    GROUP BY muslim_classification_source ORDER BY COUNT(*) DESC
""")
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]:,}')

print('\nTop 10 least confident classifications:')
c.execute("""
    SELECT id, name, Muslim_affiliation, muslim_confidence, muslim_classification_source
    FROM churches WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    ORDER BY muslim_confidence ASC LIMIT 10
""")
for r in c.fetchall():
    print(f'  id={r[0]}: {str(r[1])[:40]:40s} | {r[2]:20s} | conf={r[3]} | {r[4]}')

# Check for any NULL muslim_affiliation despite matching
still_null = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Islam' AND (muslim_affiliation IS NULL OR muslim_affiliation = '')
""").fetchone()[0]
print(f'\nStill unclassified Islam: {still_null:,}')

conn.close()

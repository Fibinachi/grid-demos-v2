import sqlite3
conn = sqlite3.connect('churches.db')

# The "fake Mexico" churches - US border states with Spanish church names
print('=== FAKE MEXICO: By state (were MX, now correctly US) ===')
for r in conn.execute("""
    SELECT state, COUNT(*) n FROM churches 
    WHERE country='US' AND name LIKE '%IGLESIA%'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 12
"""):
    print(f'  {r[0]:5s} {r[1]:>8,}')

# What do these US Spanish-name churches look like?
print('\n=== SAMPLES: Spanish-name churches now correctly US ===')
for r in conn.execute("""
    SELECT name, city, state FROM churches 
    WHERE country='US' AND (name LIKE 'IGLESIA %' OR name LIKE 'TEMPLO %')
    AND state IN ('TX','CA','AZ','NM')
    LIMIT 12
"""):
    print(f'  {r[0][:50]:50s} {r[1]:15s} {r[2]}')

# True Mexico breakdown
print('\n=== TRUE MEXICO: By state ===')
for r in conn.execute("""
    SELECT state, COUNT(*) n FROM churches WHERE country='MX' GROUP BY 1 ORDER BY 2 DESC
"""):
    print(f'  {r[0]:5s} {r[1]:>8,}')

total = conn.execute('SELECT COUNT(*) FROM churches WHERE country="MX"').fetchone()[0]
print(f'\n  True MX total: {total:,}')

# The key insight
print('\n=== THE ANSWER ===')
mx_in_tx = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND state IN ('TX','CA','AZ','NM','FL','LA','MS','AL')").fetchone()[0]
print(f'  MX churches with US state codes: {mx_in_tx} (should be 0 now)')
print(f'  These were never in Mexico - they were always US border-state churches')
print(f'  with Spanish names, caught in the Mexico bbox during Overture extraction.')

conn.close()

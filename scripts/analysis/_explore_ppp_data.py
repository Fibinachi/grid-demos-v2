"""Explore PPP loan data, RUCC codes, and election tables."""
import sqlite3
db = sqlite3.connect('churches.db')

# Election tables
print('=== Election-related tables ===')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%election%' OR name LIKE '%vote%') ORDER BY name"):
    print(r[0])

print()
print('=== All tables (filtered) ===')
for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    name = r[0]
    if any(k in name.lower() for k in ('elect', 'vote', 'census', 'rucc', 'county', 'ppp')):
        cnt = db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f'  {name}: {cnt} rows')

# RUCC structure
print()
print('=== rucc_codes columns ===')
for r in db.execute('PRAGMA table_info(rucc_codes)'): print(f'  {r[1]} {r[2]}')

print()
print('=== rucc_codes sample ===')
for r in db.execute('SELECT * FROM rucc_codes LIMIT 5'): print(r)

# How churches connect to RUCC
print()
print('=== churches county columns ===')
for r in db.execute('PRAGMA table_info(churches)'):
    name = r[1]
    if any(k in name.lower() for k in ('county', 'fips', 'rucc')):
        print(f'  {name} {r[2]}')

# Check church_census_US
print()
print('=== church_census_US columns ===')
for r in db.execute('PRAGMA table_info(church_census_US)'): print(f'  {r[1]} {r[2]}')
print(f'Rows: {db.execute("SELECT COUNT(*) FROM church_census_US").fetchone()[0]}')

# PPP matched churches: count by state, with RUCC
print()
print('=== PPP matched churches with GPS ===')
sql = """
SELECT COUNT(*) FROM sba_ppp_loans p
JOIN churches c ON p.church_id = c.id
WHERE p.latitude IS NOT NULL
"""
print(db.execute(sql).fetchone())

# Count PPP churches matched with county_fips_5
print()
print('=== PPP churches with county_fips_5 ===')
sql = """
SELECT COUNT(*) FROM sba_ppp_loans p
JOIN churches c ON p.church_id = c.id
WHERE c.county_fips_5 IS NOT NULL
"""
print(db.execute(sql).fetchone())

# Sample join: PPP + church + county
print()
print('=== Sample: PPP + church + county (5 rows) ===')
sql = """
SELECT p.loan_amount, p.jobs_reported, p.borrower_city, p.borrower_state,
       c.county_fips_5, c.name, c.faith, c.tradition
FROM sba_ppp_loans p
JOIN churches c ON p.church_id = c.id
WHERE p.latitude IS NOT NULL
LIMIT 5
"""
for r in db.execute(sql): print(r)

db.close()

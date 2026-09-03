import sqlite3
conn = sqlite3.connect('churches.db')

total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

print('=== DATABASE TOTALS ===')
print(f'Total churches: {total:,}')

# Source distribution
print('\n=== BY SOURCE ===')
for row in conn.execute('''
    SELECT COALESCE(source, 'NULL') as src, COUNT(*) as n
    FROM churches
    GROUP BY 1 ORDER BY 2 DESC
'''):
    print(f'  {row[0]:30s} {row[1]:>8,}')

# Country breakdown
print('\n=== BY COUNTRY ===')
for row in conn.execute('''
    SELECT COALESCE(country, 'NULL') as c, COUNT(*) as n
    FROM churches
    GROUP BY 1 ORDER BY 2 DESC
'''):
    print(f'  {row[0]:10s} {row[1]:>8,}')

# Enrichment rates
print('\n=== ENRICHMENT RATES ===')
checks = [
    ('Has coordinates', "latitude IS NOT NULL AND longitude IS NOT NULL"),
    ('Has county_fips', "county_fips IS NOT NULL AND county_fips != ''"),
    ('Has tract_fips', "tract_fips IS NOT NULL AND tract_fips != ''"),
    ('Has denomination', "denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'"),
    ('Has website', "website IS NOT NULL AND website != ''"),
    ('Has email', "email IS NOT NULL AND email != ''"),
    ('Has phone', "phone IS NOT NULL AND phone != ''"),
    ('Has attendance_est', "attendance_est IS NOT NULL AND attendance_est > 0"),
    ('Has attendance_arda', "attendance_arda IS NOT NULL AND attendance_arda > 0"),
    ('Has either attendance', "COALESCE(attendance_est, attendance_arda) > 0"),
    ('Has county_name', "county_name IS NOT NULL AND county_name != ''"),
]
for label, cond in checks:
    try:
        n = conn.execute(f'SELECT COUNT(*) FROM churches WHERE {cond}').fetchone()[0]
        pct = 100 * n / total if total > 0 else 0
        print(f'  {label:25s}: {n:>8,} ({pct:5.1f}%)')
    except Exception as e:
        print(f'  {label:25s}: ERROR ({e})')

# Geocode source
print('\n=== GEOCODE SOURCE ===')
for row in conn.execute('''
    SELECT COALESCE(geocode_source, 'NULL') as gs, COUNT(*) as n
    FROM churches WHERE latitude IS NOT NULL
    GROUP BY 1 ORDER BY 2 DESC
'''):
    print(f'  {row[0]:30s} {row[1]:>8,}')

# Top denominations
print('\n=== TOP DENOMINATIONS (by count) ===')
for row in conn.execute('''
    SELECT denomination, COUNT(*) as n
    FROM churches
    WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'
    GROUP BY 1 ORDER BY 2 DESC
    LIMIT 15
'''):
    print(f'  {row[0][:40]:40s} {row[1]:>8,}')

# US State distribution
print('\n=== TOP STATES ===')
for row in conn.execute('''
    SELECT COALESCE(state, 'NULL') as st, COUNT(*) as n
    FROM churches
    GROUP BY 1 ORDER BY 2 DESC
    LIMIT 15
'''):
    print(f'  {row[0]:10s} {row[1]:>8,}')

# Quick attendance stats
print('\n=== ATTENDANCE STATS ===')
has_att = conn.execute('SELECT COUNT(*) FROM churches WHERE COALESCE(attendance_est, attendance_arda) > 0').fetchone()[0]
avg_att = conn.execute('SELECT ROUND(AVG(COALESCE(attendance_est, attendance_arda))) FROM churches WHERE COALESCE(attendance_est, attendance_arda) > 0').fetchone()[0]
total_att = conn.execute('SELECT SUM(COALESCE(attendance_est, attendance_arda)) FROM churches WHERE COALESCE(attendance_est, attendance_arda) > 0').fetchone()[0]
print(f'  Churches with attendance: {has_att:,}')
print(f'  Average attendance: {avg_att:,.0f}')
print(f'  Total weekly attendance: {total_att:,.0f}')

# Just-check churchunion import status
print('\n=== CHURCHUNION IMPORT STATUS ===')
new = conn.execute("SELECT COUNT(*) FROM churches WHERE source = 'churchunion_scraper'").fetchone()[0]
dup = conn.execute("SELECT COUNT(*) FROM church_sources WHERE source_name = 'churchunion_scraper'").fetchone()[0]
print(f'  New churchunion churches: {new:,}')
print(f'  Duplicates logged: {dup:,}')

conn.close()

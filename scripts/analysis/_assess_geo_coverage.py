"""Assess current geographic data coverage in churches.db"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# What's in address_components for location data?
print('=== ADDRESS COMPONENTS DISTRIBUTION ===')
c.execute('SELECT component_type, COUNT(*) as cnt FROM address_components GROUP BY component_type ORDER BY cnt DESC')
rows = c.fetchall()
for r in rows:
    print(f'{r[0]:30s} {r[1]:>10,}')
print()

# How many have country in churches table?
print('=== CHURCHES TABLE LOCATION COVERAGE ===')
c.execute('SELECT COUNT(*) FROM churches')
total = c.fetchone()[0]

for col in ['country', 'city', 'state', 'county', 'zip']:
    c.execute(f'SELECT COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != \'\'')
    filled = c.fetchone()[0]
    print(f'{col:15s} filled: {filled:>10,} / {total:,} ({100*filled/total:.1f}%)')

# How many have coordinates?
c.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL')
with_gps = c.fetchone()[0]
print(f'\nwith GPS coords: {with_gps:>10,} / {total:,} ({100*with_gps/total:.1f}%)')

# Missing country but have GPS
queries = [
    ("missing country (but have GPS)", "country"),
    ("missing city (but have GPS)", "city"),
    ("missing state (but have GPS)", "state"),
    ("missing county (but have GPS)", "county"),
    ("missing country+city (GPS)", None),
]
for label, col in queries:
    if col:
        c.execute(f'SELECT COUNT(*) FROM churches WHERE ({col} IS NULL OR {col} = \'\') AND latitude IS NOT NULL AND longitude IS NOT NULL')
    else:
        c.execute('SELECT COUNT(*) FROM churches WHERE (country IS NULL OR country = \'\') AND (city IS NULL OR city = \'\') AND latitude IS NOT NULL AND longitude IS NOT NULL')
    print(f'{label:40s} {c.fetchone()[0]:>10,}')

# Country-level breakdown of churches with GPS but no country
print('\n=== TOP COUNTRIES (by GPS, where country is missing) ===')
c.execute('''
    SELECT 
        CASE 
            WHEN latitude BETWEEN 24 AND 50 AND longitude BETWEEN -125 AND -66 THEN 'US'
            WHEN latitude BETWEEN 41 AND 85 AND longitude BETWEEN -145 AND -52 THEN 'CA'
            WHEN latitude BETWEEN -60 AND 15 AND longitude BETWEEN -82 AND -34 THEN 'BR'
            WHEN latitude BETWEEN 35 AND 72 AND longitude BETWEEN -10 AND 40 THEN 'EU'
            WHEN latitude BETWEEN -35 AND 35 AND longitude BETWEEN 68 AND 100 THEN 'IN'
            WHEN latitude BETWEEN -50 AND -10 AND longitude BETWEEN 110 AND 160 THEN 'AU/OC'
            ELSE 'Other'
        END as region_guess,
        COUNT(*) as cnt
    FROM churches 
    WHERE (country IS NULL OR country = '') AND latitude IS NOT NULL AND longitude IS NOT NULL
    GROUP BY region_guess
    ORDER BY cnt DESC
''')
for r in c.fetchall():
    print(f'{r[0]:15s} {r[1]:>10,}')

# Sample of GPS records with no country
print('\n=== SAMPLE: GPS but no country (first 10) ===')
c.execute('''
    SELECT rowid, latitude, longitude, COALESCE(name, '(no name)') as name
    FROM churches 
    WHERE (country IS NULL OR country = '') AND latitude IS NOT NULL AND longitude IS NOT NULL
    LIMIT 10
''')
for r in c.fetchall():
    print(f'  rowid={r[0]:>7} lat={r[1]:.4f} lon={r[2]:.4f}  {r[3][:60]}')

# How many are in address_components already?
print('\n=== ADDRESS COMPONENTS COVERAGE ===')
for comp in ['city', 'state', 'country', 'region']:
    c.execute(f'SELECT COUNT(DISTINCT church_rowid) FROM address_components WHERE component_type = ?', (comp,))
    cnt = c.fetchone()[0]
    print(f'{comp:15s} {cnt:>10,} distinct church_rowids')

conn.close()

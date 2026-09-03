"""Explore Mexican church data and existing infrastructure."""
import gw_db

db = gw_db.connect()

# Mexican churches count
cur = db.execute('SELECT COUNT(*) FROM churches WHERE country = ?', ('MX',))
print(f'Mexican churches: {cur.fetchone()[0]}')

# Check columns in churches
cur = db.execute('PRAGMA table_info(churches)')
cols = cur.fetchall()
print(f'\nChurches table columns: {len(cols)}')

# Check church_enrichment schema
cur = db.execute('PRAGMA table_info(church_enrichment)')
cols = cur.fetchall()
print(f'\nchurch_enrichment columns:')
for c in cols:
    print(f'  {c[1]:35s} {c[2]:15s} nullable={c[3]}')

# List all tables
cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [t[0] for t in cur.fetchall()]
print(f'\nAll tables ({len(tables)}):')
for t in tables:
    print(f'  {t}')

# Check the church_postal_admin table (has MX columns)
cur = db.execute('PRAGMA table_info(church_postal_admin)')
cols = cur.fetchall()
print(f'\nchurch_postal_admin columns:')
for c in cols:
    print(f'  {c[1]:35s} {c[2]:15s} nullable={c[3]}')

# Sample MX churches
cur = db.execute('''
    SELECT id, name, city, state, admin_region, faith, latitude, longitude, source
    FROM churches 
    WHERE country = ? AND city IS NOT NULL 
    LIMIT 10
''', ('MX',))
print(f'\nSample MX churches:')
for row in cur.fetchall():
    print(f'  {row}')

# MX states distribution
cur = db.execute('''
    SELECT state, COUNT(*) as cnt 
    FROM churches 
    WHERE country = ? AND state IS NOT NULL 
    GROUP BY state 
    ORDER BY cnt DESC
    LIMIT 20
''', ('MX',))
print(f'\nMX state distribution:')
for row in cur.fetchall():
    print(f'  {row[0]:30s} {row[1]}')

# Check county_census_us table (US example) as template
cur = db.execute('PRAGMA table_info(county_census_us)')
cols = cur.fetchall()
print(f'\ncounty_census_us columns:')
for c in cols:
    print(f'  {c[1]:35s} {c[2]:15s} nullable={c[3]}')

# Check existing geo data
import os
print(f'\nChecking for MX shapefiles...')
geo_dir = 'data/natural_earth'
for root, dirs, files in os.walk(geo_dir):
    for f in files:
        if 'mexic' in f.lower() or 'mx' in f.lower()[:4]:
            print(f'  {os.path.join(root, f)}')

db.close()

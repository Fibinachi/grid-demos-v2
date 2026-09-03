"""Assess current state of non-US records for reverse geocoding."""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Total non-US records with GPS
c.execute('''
    SELECT COUNT(*) FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
''')
total = c.fetchone()[0]
print(f'Non-US records with GPS: {total:,}')

# Already have country
c.execute('''
    SELECT COUNT(*) FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
      AND country IS NOT NULL AND country != ''
''')
has_country = c.fetchone()[0]
print(f'    with country already: {has_country:,}')

# Need city
c.execute('''
    SELECT COUNT(*) FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
      AND (city IS NULL OR city = '')
''')
need_city = c.fetchone()[0]
print(f'    needing city: {need_city:,}')

# Need state
c.execute('''
    SELECT COUNT(*) FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
      AND (state IS NULL OR state = '')
''')
need_state = c.fetchone()[0]
print(f'    needing state: {need_state:,}')

# Already have state
c.execute('''
    SELECT COUNT(*) FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
      AND state IS NOT NULL AND state != ''
''')
has_state = c.fetchone()[0]
print(f'    with state already: {has_state:,}')

# Geocode sources
c.execute('''
    SELECT COALESCE(geocode_source, 'NULL') as src, COUNT(*) as cnt FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
    GROUP BY src ORDER BY cnt DESC
    LIMIT 10
''')
print(f'\nGeocode sources for non-US:')
for src, cnt in c.fetchall():
    print(f'  {src:30s} {cnt:>8,}')

# Top countries
c.execute('''
    SELECT COALESCE(country, 'NULL') as c, COUNT(*) as cnt FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
    GROUP BY c ORDER BY cnt DESC
    LIMIT 20
''')
print(f'\nTop 20 countries:')
for cname, cnt in c.fetchall():
    print(f'  {cname or "NULL":30s} {cnt:>8,}')

# Also check what city coverage looks like per top countries
c.execute('''
    SELECT COALESCE(country, 'NULL') as c,
           COUNT(*) as total,
           SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as with_city
    FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
    GROUP BY c ORDER BY total DESC
    LIMIT 15
''')
print(f'\nCity coverage per country (top 15):')
print(f'  {"Country":20s} {"Total":>8s} {"With City":>10s} {"Pct":>6s}')
for cname, total, with_city in c.fetchall():
    pct = with_city / total * 100 if total > 0 else 0
    print(f'  {cname or "NULL":20s} {total:>8,} {with_city:>10,} {pct:>5.1f}%')

conn.close()

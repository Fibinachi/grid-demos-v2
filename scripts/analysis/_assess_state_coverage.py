"""Check state coverage per country to see what Admin 1 was already applied."""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

c.execute('''
    SELECT COALESCE(country, 'NULL') as c,
           COUNT(*) as total,
           SUM(CASE WHEN state IS NOT NULL AND state != '' THEN 1 ELSE 0 END) as with_state,
           SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as with_city
    FROM churches 
    WHERE latitude IS NOT NULL AND longitude IS NOT NULL
      AND (country IS NULL OR country = '' OR country != 'US')
    GROUP BY c ORDER BY total DESC
    LIMIT 25
''')
print(f'{"Country":20s} {"Total":>8s} {"State":>8s} {"State%":>7s} {"City":>8s} {"City%":>7s}')
print('-' * 58)
for cname, total, with_state, with_city in c.fetchall():
    spct = with_state / total * 100 if total > 0 else 0
    cpct = with_city / total * 100 if total > 0 else 0
    print(f'{cname or "NULL":20s} {total:>8,} {with_state:>8,} {spct:>6.1f}% {with_city:>8,} {cpct:>6.1f}%')

# Check what data already exists in address_components for non-US
c.execute('''
    SELECT COUNT(DISTINCT ac.address_id) as addr_count,
           COUNT(*) as comp_count
    FROM address_components ac
    JOIN church_addresses ca ON ac.address_id = ca.address_id
    JOIN churches ch ON ca.church_rowid = ch.rowid
    WHERE (ch.country IS NULL OR ch.country = '' OR ch.country != 'US')
''')
addr_count, comp_count = c.fetchone()
print(f'\nNon-US records with address_components: {addr_count:,} addresses, {comp_count:,} components')

# Check church_addresses for non-US
c.execute('''
    SELECT COUNT(*) FROM church_addresses ca
    JOIN churches ch ON ca.church_rowid = ch.rowid
    WHERE (ch.country IS NULL OR ch.country = '' OR ch.country != 'US')
''')
print(f'Non-US records in church_addresses: {c.fetchone()[0]:,}')

conn.close()

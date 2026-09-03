"""Quick MX data check."""
import gw_db

db = gw_db.connect()

# MX churches with coordinates
cur = db.execute(
    'SELECT COUNT(*) FROM churches WHERE country = ? AND latitude IS NOT NULL',
    ('MX',)
)
print(f'MX churches with coords: {cur.fetchone()[0]:,} / 80,624')

# Top MX states/locations
cur = db.execute(
    """SELECT COALESCE(state, city, '(unknown)') as loc, COUNT(*) as cnt 
       FROM churches WHERE country = ? 
       GROUP BY loc ORDER BY cnt DESC LIMIT 10""",
    ('MX',)
)
print('\nMX top locations:')
for r in cur:
    print(f'  {r[0]:30s} {r[1]:,}')

# All distinct states
cur = db.execute(
    'SELECT DISTINCT state FROM churches WHERE country = ? AND state IS NOT NULL ORDER BY state',
    ('MX',)
)
states = [r[0] for r in cur.fetchall()]
print(f'\nAll MX states ({len(states)}):')
for s in states:
    print(f'  {s}')

# Already populated MX fields
cur = db.execute(
    """SELECT COUNT(*) FROM church_enrichment ce
       JOIN churches ch ON ch.id = ce.church_id
       WHERE ch.country = ? AND (ce.mx_division_id IS NOT NULL OR ce.mx_division_name IS NOT NULL)""",
    ('MX',)
)
print(f'\nMX division data already populated: {cur.fetchone()[0]:,}')
db.close()

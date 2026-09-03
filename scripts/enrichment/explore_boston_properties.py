"""Explore Boston churches in DB and prepare for CKAN property matching."""
from gw_db import get_db

db = get_db()

# Total Boston churches
boston = db.execute("SELECT COUNT(*) FROM churches WHERE city='BOSTON' AND state='MA'").fetchone()[0]
print(f'Boston churches: {boston}')

# By faith
faiths = db.execute("SELECT faith, COUNT(*) as cnt FROM churches WHERE city='BOSTON' AND state='MA' GROUP BY faith ORDER BY cnt DESC LIMIT 20").fetchall()
print('\nBy faith:')
for f in faiths:
    print(f'  {f[0]}: {f[1]}')

# Check enrichment columns
cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()]
relevant = [c for c in cols if any(x in c.lower() for x in ['value','area','tax','gross','assess','parcel','pid','boston','property','valuation','enrich'])]
print(f'\nRelevant columns: {relevant}')

# Check church_contact_values for Boston addresses
addr_count = db.execute("SELECT COUNT(DISTINCT church_id) FROM church_contact_values c JOIN churches ch ON c.church_id=ch.id WHERE ch.city='BOSTON' AND ch.state='MA' AND c.contact_type IN ('address','street_address')").fetchone()[0]
print(f'\nBoston churches with address in contact_values: {addr_count}')

# Sample some Boston churches with addresses
samples = db.execute("""
    SELECT ch.id, ch.name, ch.faith, ch.lat, ch.lon, 
           cc.value as address
    FROM churches ch
    LEFT JOIN church_contact_values cc ON cc.church_id = ch.id AND cc.contact_type IN ('address','street_address')
    WHERE ch.city='BOSTON' AND ch.state='MA'
    LIMIT 15
""").fetchall()
print('\nSamples:')
for s in samples:
    print(f'  #{s[0]}: {s[1]} | {s[2]} | {s[5]} | ({s[3]},{s[4]})')

# Also check how many have GPS coordinates
with_gps = db.execute("SELECT COUNT(*) FROM churches WHERE city='BOSTON' AND state='MA' AND lat IS NOT NULL AND lon IS NOT NULL").fetchone()[0]
print(f'\nBoston churches with GPS: {with_gps}/{boston}')

"""Fix country using state/province codes — authoritative, no guesswork."""
import sqlite3
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')

# Canadian province codes
CA_PROVINCES = ('ON','QC','BC','AB','MB','SK','NS','NB','NL','PE','YT','NT','NU')

# Mexican state codes (from Overture data)
MX_STATES = ('CMX','SLP','BCS','BCN','CHH','CHP','COA','COL','DIF','DGO',
             'GRO','GUA','HID','JAL','MCH','MEX','MOA','NAY','NLE','OAX',
             'PUE','QUE','ROO','SIN','SON','TAB','TAM','TLA','VER','YUC','ZAC')

# US state codes (all 50 + DC + territories)
US_STATES = ('AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID',
             'IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO',
             'MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA',
             'RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY',
             'PR','VI','GU','MP','AS')

print('=== BEFORE ===')
for r in conn.execute('SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC'):
    print(f'  {r[0]:5s} {r[1]:>10,}')

# Fix by state code (authoritative)
n1 = conn.execute(f"UPDATE churches SET country='CA' WHERE state IN ({','.join('?'*len(CA_PROVINCES))}) AND country!='CA'", 
                  CA_PROVINCES).rowcount
print(f'\nSet CA by province code: {n1:,}')

n2 = conn.execute(f"UPDATE churches SET country='MX' WHERE state IN ({','.join('?'*len(MX_STATES))}) AND country!='MX'",
                  MX_STATES).rowcount
print(f'Set MX by state code: {n2:,}')

n3 = conn.execute(f"UPDATE churches SET country='US' WHERE state IN ({','.join('?'*len(US_STATES))}) AND country!='US'",
                  US_STATES).rowcount
print(f'Set US by state code: {n3:,}')

conn.commit()

print('\n=== AFTER ===')
for r in conn.execute('SELECT country, COUNT(*) n FROM churches GROUP BY 1 ORDER BY 2 DESC'):
    print(f'  {r[0]:5s} {r[1]:>10,}')

# Samples
print('\n=== TRUE CANADIAN ===')
for r in conn.execute("SELECT name, city, state, country FROM churches WHERE country='CA' LIMIT 5").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]:3s} country={r[3]}')

print('\n=== TRUE MEXICAN ===')
for r in conn.execute("SELECT name, city, state, country FROM churches WHERE country='MX' LIMIT 5").fetchall():
    print(f'  {r[0][:45]:45s} {r[1]:15s} {r[2]:3s} country={r[3]}')

# What's left unclassified?
other = conn.execute("SELECT COUNT(*) FROM churches WHERE country NOT IN ('US','CA','MX','EU')").fetchone()[0]
null_country = conn.execute("SELECT COUNT(*) FROM churches WHERE country IS NULL OR country=''").fetchone()[0]
print(f'\nOther/unknown country: {other:,}')
print(f'NULL country: {null_country:,}')

conn.close()
print('Done.')

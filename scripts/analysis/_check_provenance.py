"""Check source positions and CRA/OSM details."""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')
c = db.cursor()

# Key source positions in ID order
queries = [
    ('cra_2018', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source LIKE '%cra_2018%'"),
    ('osm_import', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source LIKE '%osm_import%'"),
    ('irs (pure)', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='irs'"),
    ('irs+holy_sites', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='irs+holy_sites_enrichment'"),
    ('contacts', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='contacts'"),
    ('holy_sites_import', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='holy_sites_import'"),
    ('churchunion', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='churchunion_scraper'"),
    ('overture_full', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='overture_full'"),
    ('wikidata_sa', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='wikidata_sa_mosques'"),
    ('wikidata', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='wikidata'"),
    ('csv_import_india_osm', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='csv_import_india_osm'"),
    ('masstimes', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='masstimes_nationwide+holy_sites_enrichment'"),
    ('catholic_diocese', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='catholic_diocese_scrape'"),
    ('ag_directory', "SELECT MIN(id), MAX(id), COUNT(*) FROM churches WHERE source='ag_directory'"),
]

print('=== SOURCE POSITIONS IN ID SPACE ===')
for name, sql in queries:
    c.execute(sql)
    r = c.fetchone()
    if r[0] is not None:
        print(f'  {name:25s}  first_id={r[0]:>8,}  last_id={r[1]:>8,}  count={r[2]:>8,}')
    else:
        print(f'  {name:25s}  NOT FOUND')

print()
print('=== FIRST 10 RECORDS ===')
c.execute('SELECT id, substr(name,1,30), city, country, source FROM churches ORDER BY id ASC LIMIT 10')
for r in c.fetchall():
    print(f'  id={r[0]:>8}  src={str(r[4])[:60]}')

print()
print('=== ALL DISTINCT cra-like SOURCES ===')
c.execute("SELECT DISTINCT source FROM churches WHERE source LIKE '%cra%'")
for r in c.fetchall():
    c2 = db.cursor()
    c2.execute('SELECT COUNT(*) FROM churches WHERE source = ?', (r[0],))
    print(f'  {str(r[0]):60s}  cnt={c2.fetchone()[0]:>8,}')

print()
print('=== ALL DISTINCT osm-like SOURCES ===')
c.execute("SELECT DISTINCT source FROM churches WHERE source LIKE '%osm%'")
for r in c.fetchall():
    c2 = db.cursor()
    c2.execute('SELECT COUNT(*) FROM churches WHERE source = ?', (r[0],))
    print(f'  {str(r[0]):60s}  cnt={c2.fetchone()[0]:>8,}')

print()
print('=== ALL DISTINCT irs-like SOURCES ===')
c.execute("SELECT DISTINCT source FROM churches WHERE source LIKE '%irs%'")
for r in c.fetchall():
    c2 = db.cursor()
    c2.execute('SELECT COUNT(*) FROM churches WHERE source = ?', (r[0],))
    print(f'  {str(r[0]):60s}  cnt={c2.fetchone()[0]:>8,}')

db.close()

"""GRID Overview Stats Generator"""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')
cur = db.cursor()

print('=' * 60)
print('GRID — Global Religious Infrastructure Database')
print('Overview Statistics')
print('=' * 60)

print('\n=== 1. CORE SIZE & COVERAGE ===')
cur.execute('SELECT COUNT(*) FROM churches')
total = cur.fetchone()[0]
print(f'  Total global holy sites:     {total:,}')

cur.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND latitude != 0 AND longitude != 0')
geocoded = cur.fetchone()[0]
print(f'  Geocoded (lat/lon):          {geocoded:,}  ({geocoded/total*100:.1f}%)')

cur.execute('SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL OR faith IS NOT NULL')
meta = cur.fetchone()[0]
print(f'  With faith/denom metadata:   {meta:,}  ({meta/total*100:.1f}%)')

cur.execute('SELECT COUNT(DISTINCT country) FROM churches WHERE country IS NOT NULL AND country != ""')
countries = cur.fetchone()[0]
print(f'  Countries/territories:       {countries}')

cur.execute('SELECT COUNT(DISTINCT faith) FROM churches WHERE faith IS NOT NULL')
faiths = cur.fetchone()[0]
print(f'  Religious traditions:        {faiths}')

cur.execute('SELECT COUNT(DISTINCT denomination) FROM churches WHERE denomination IS NOT NULL')
denoms = cur.fetchone()[0]
print(f'  Distinct denominations:      {denoms}')

# Null faith count
cur.execute('SELECT COUNT(*) FROM churches WHERE faith IS NULL')
null_faith = cur.fetchone()[0]
print(f'  Faith unclassified:          {null_faith:,}  ({null_faith/total*100:.1f}%)')

print('\n=== 2. FAITH BREAKDOWN ===')
cur.execute("SELECT COALESCE(NULLIF(faith,''), 'NULL') as f, COUNT(*) as cnt FROM churches GROUP BY f ORDER BY cnt DESC")
for f in cur.fetchall():
    print(f'  {f[0]:20s} {f[1]:>10,}  ({f[1]/total*100:.1f}%)')

print('\n=== 3. DATA SOURCES ===')
cur.execute('SELECT COALESCE(NULLIF(source,""),"unknown") as src, COUNT(*) as cnt FROM churches GROUP BY src ORDER BY cnt DESC')
srcs = cur.fetchall()
for s in srcs:
    print(f'  {s[0]:40s} {s[1]:>10,}  ({s[1]/total*100:.1f}%)')

print('\n=== 4. ENRICHMENT TABLES ===')
for tbl in ['church_enrichment', 'church_contacts', 'provenance_log', 'enrichment_change_log', 'church_sources']:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'  {tbl:30s} {cur.fetchone()[0]:>10,} rows')
    except:
        print(f'  {tbl:30s} (not found)')

print('\n=== 5. DECOMPOSED TABLES ===')
for tbl in ['county_census_us', 'church_fcc', 'church_metro_area', 'church_nrhp', 'church_gnis', 'rucc_codes', 'church_broadband', 'church_classification_meta', 'church_postal_admin']:
    try:
        cur.execute(f'SELECT COUNT(*) FROM {tbl}')
        print(f'  {tbl:30s} {cur.fetchone()[0]:>10,} rows')
    except:
        print(f'  {tbl:30s} (not found)')

print('\n=== 6. COUNTRY BREAKDOWN (top 25) ===')
cur.execute('SELECT country, COUNT(*) as cnt FROM churches WHERE country IS NOT NULL AND country != "" GROUP BY country ORDER BY cnt DESC LIMIT 25')
for c in cur.fetchall():
    print(f'  {c[0]:5s} {c[1]:>10,}')

print('\n=== 7. LANDMARK TYPE BREAKDOWN ===')
cur.execute("SELECT COALESCE(NULLIF(landmark_type,''),'none') as lt, COUNT(*) as cnt FROM churches GROUP BY lt ORDER BY cnt DESC")
for l in cur.fetchall():
    print(f'  {l[0]:30s} {l[1]:>10,}')

print('\n=== 8. DATABASE SIZE ===')
import os
size_mb = os.path.getsize('E:\\grid\\churches.db') / (1024*1024)
print(f'  churches.db:                 {size_mb:,.0f} MB')

print('\n=== 9. TABLES COUNT ===')
cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
print(f'  Total tables:                {cur.fetchone()[0]}')

# Count rows in all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cur.fetchall()
total_rows = 0
print('\n  All tables:')
for t in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM [{t[0]}]')
        r = cur.fetchone()[0]
        total_rows += r
        print(f'    {t[0]:35s} {r:>12,}')
    except:
        pass
print(f'    {"(total)":35s} {total_rows:>12,}')

print('\n=== 10. CONTACT COVERAGE ===')
cur.execute('SELECT COUNT(*) FROM church_contacts WHERE email IS NOT NULL')
print(f'  Emails:                      {cur.fetchone()[0]:>10,}')
cur.execute('SELECT COUNT(*) FROM church_contacts WHERE website IS NOT NULL')
print(f'  Websites:                    {cur.fetchone()[0]:>10,}')
cur.execute('SELECT COUNT(*) FROM church_contacts WHERE phone IS NOT NULL')
print(f'  Phones:                      {cur.fetchone()[0]:>10,}')

print('\nDone.')
db.close()

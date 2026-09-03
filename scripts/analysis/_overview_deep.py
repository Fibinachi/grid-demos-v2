"""Deeper GRID overview stats"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding='utf-8')
db = sqlite3.connect('E:\\grid\\churches.db')
cur = db.cursor()

print('=== DEEPER STATS ===\n')

# US church coverage
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "US"')
us_total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "US" AND faith IS NOT NULL')
us_faith = cur.fetchone()[0]
print(f'US sites: {us_total:,} ({us_faith/us_total*100:.1f}% with faith metadata)')

# Canada
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "CA"')
ca_total = cur.fetchone()[0]
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "CA" AND faith IS NOT NULL')
ca_faith = cur.fetchone()[0]
print(f'Canada sites: {ca_total:,} ({ca_faith/ca_total*100:.1f}% with faith metadata)')

# Mosques
cur.execute('SELECT COUNT(*) FROM churches WHERE faith = "Islam"')
mosques = cur.fetchone()[0]
print(f'\nMosques: {mosques:,}')

cur.execute('SELECT COUNT(*) FROM churches WHERE landmark_type = "mosque"')
lm_mosques = cur.fetchone()[0]
print(f'Mosques (landmark_type): {lm_mosques:,}')

# Mosques by country top 10
cur.execute('SELECT country, COUNT(*) FROM churches WHERE faith = "Islam" GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10')
print('Mosques by country (top 10):')
for r in cur.fetchall():
    print(f'  {r[0]:5s} {r[1]:>10,}')

# US Christian breakdown
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "US" AND faith = "Christian"')
us_christian = cur.fetchone()[0]
print(f'\nUS Christian sites: {us_christian:,}')

# Japan Shinto/Buddhist
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "JP" AND faith = "Shinto"')
jp_shinto = cur.fetchone()[0]
print(f'Japan Shinto: {jp_shinto:,}')
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "JP" AND faith = "Buddhist"')
jp_buddhist = cur.fetchone()[0]
print(f'Japan Buddhist: {jp_buddhist:,}')
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "JP"')
jp_total = cur.fetchone()[0]
print(f'Japan total: {jp_total:,}')

# US landmarks
cur.execute('SELECT COALESCE(NULLIF(landmark_type,""),"(none)") as lt, COUNT(*) FROM churches WHERE country = "US" GROUP BY lt ORDER BY COUNT(*) DESC')
print('\nUS landmark type breakdown:')
for r in cur.fetchall():
    print(f'  {r[0]:20s} {r[1]:>10,}')

# Top Christian denominations in US
cur.execute('SELECT denomination, COUNT(*) FROM churches WHERE country = "US" AND faith = "Christian" AND denomination IS NOT NULL GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 20')
print('\nTop US Christian denominations:')
for r in cur.fetchall():
    print(f'  {r[0]:40s} {r[1]:>10,}')

# Dedup stats
cur.execute('SELECT COUNT(*) FROM holy_sites')
hs = cur.fetchone()[0]
print(f'\nholy_sites table (pre-dedup): {hs:,}')
cur.execute('SELECT COUNT(*) FROM churches')
ch = cur.fetchone()[0]
print(f'churches table (post-dedup): {ch:,}')
print(f'Dedup reduction: {hs - ch:,} rows ({(hs-ch)/hs*100:.1f}%)')

# India detail
cur.execute('SELECT faith, COUNT(*) FROM churches WHERE country = "IN" AND faith IS NOT NULL GROUP BY faith ORDER BY COUNT(*) DESC')
print('\nIndia faith breakdown:')
for r in cur.fetchall():
    print(f'  {r[0]:20s} {r[1]:>10,}')

# Saudi Arabia
cur.execute('SELECT faith, COUNT(*) FROM churches WHERE country = "SA" AND faith IS NOT NULL GROUP BY faith ORDER BY COUNT(*) DESC')
print('\nSaudi Arabia faith breakdown:')
for r in cur.fetchall():
    print(f'  {r[0]:20s} {r[1]:>10,}')

# Countries with most sites
cur.execute('SELECT country, COUNT(*) as cnt FROM churches WHERE country IS NOT NULL AND country != "" GROUP BY country ORDER BY cnt DESC')
all_countries = cur.fetchall()
print(f'\nTotal countries with data: {len(all_countries)}')
ct_1k = sum(1 for c in all_countries if c[1] >= 1000)
ct_10k = sum(1 for c in all_countries if c[1] >= 10000)
ct_100k = sum(1 for c in all_countries if c[1] >= 100000)
print(f'Countries with 1k+ sites: {ct_1k}')
print(f'Countries with 10k+ sites: {ct_10k}')
print(f'Countries with 100k+ sites: {ct_100k}')

# Atlantic coverage (US/Canada/UK combined)
atlantic = us_total + ca_total
cur.execute('SELECT COUNT(*) FROM churches WHERE country = "GB"')
atlantic += cur.fetchone()[0]
print(f'\nUS+CA+GB combined: {atlantic:,}')

# Christian sub-traditions (enrichment data?)
try:
    cur.execute('SELECT COUNT(DISTINCT tradition) FROM church_enrichment WHERE tradition IS NOT NULL')
    traditions = cur.fetchone()[0]
    print(f'\nDistinct Christian traditions in enrichment: {traditions}')
    cur.execute('SELECT tradition, COUNT(*) FROM church_enrichment WHERE tradition IS NOT NULL GROUP BY tradition ORDER BY COUNT(*) DESC LIMIT 20')
    for r in cur.fetchall():
        print(f'  {r[0]:30s} {r[1]:>10,}')
except Exception as e:
    print(f'Tradition query error: {e}')

# Broadway style: churches with enrichment have addresses?
cur.execute('SELECT COUNT(*) FROM church_addresses')
addr = cur.fetchone()[0]
print(f'\nAddresses: {addr:,}')

cur.execute('SELECT COUNT(DISTINCT church_id) FROM church_addresses')
addr_churches = cur.fetchone()[0]
print(f'Churches with addresses: {addr_churches:,}')

# Countries list
cur.execute('SELECT DISTINCT country FROM churches WHERE country IS NOT NULL AND country != "" ORDER BY country')
print(f'\nCountry codes:')
countries_list = [r[0] for r in cur.fetchall()]
print(', '.join(countries_list))

db.close()

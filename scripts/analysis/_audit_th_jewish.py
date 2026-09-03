"""Audit: are there really 305 synagogues in Thailand?"""
import sqlite3

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

# Total
c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND faith=?", ('TH', 'Jewish'))
total = c.fetchone()[0]
print(f'Total Jewish entries in Thailand: {total}')

# By source
c.execute("SELECT source, COUNT(*) as cnt FROM churches WHERE country=? AND faith=? GROUP BY source ORDER BY cnt DESC", ('TH', 'Jewish'))
print('\nBy source:')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Name analysis
c.execute("SELECT name, city, source, latitude, longitude FROM churches WHERE country=? AND faith=? ORDER BY name LIMIT 40", ('TH', 'Jewish'))
print('\nFirst 40 entries:')
for r in c.fetchall():
    print(f'  {r[0]:40s} | {str(r[1] or ""):15s} | {r[2]:20s} | {r[3]}, {r[4]}')

# Count unique names
c.execute("SELECT COUNT(DISTINCT name) FROM churches WHERE country=? AND faith=?", ('TH', 'Jewish'))
distinct = c.fetchone()[0]
print(f'\nDistinct names: {distinct}')

# Group by normalized name patterns
c.execute("""
    SELECT CASE
        WHEN LOWER(name) LIKE '%synagogue%' THEN 'synagogue'
        WHEN LOWER(name) LIKE '%temple%' THEN 'temple'
        WHEN LOWER(name) LIKE '%mosque%' THEN 'mosque'
        WHEN LOWER(name) LIKE '%church%' THEN 'church'
        WHEN LOWER(name) LIKE '%shul%' THEN 'shul'
        WHEN LOWER(name) LIKE '%center%' THEN 'center'
        WHEN LOWER(name) LIKE '%house%' THEN 'house'
        ELSE 'other'
    END as category, COUNT(*) as cnt
    FROM churches WHERE country=? AND faith=?
    GROUP BY category ORDER BY cnt DESC
""", ('TH', 'Jewish'))
print('\nName pattern breakdown:')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Show "other" category names
c.execute("""
    SELECT name FROM churches WHERE country=? AND faith=?
    AND LOWER(name) NOT LIKE '%synagogue%'
    AND LOWER(name) NOT LIKE '%temple%'
    AND LOWER(name) NOT LIKE '%mosque%'
    AND LOWER(name) NOT LIKE '%church%'
    AND LOWER(name) NOT LIKE '%shul%'
    AND LOWER(name) NOT LIKE '%center%'
    AND LOWER(name) NOT LIKE '%house%'
    ORDER BY name LIMIT 20
""", ('TH', 'Jewish'))
print('\n"Other" category sample:')
for r in c.fetchall():
    print(f'  {r[0]}')

# Coordinates check: are they all in Thailand roughly?
c.execute("SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude) FROM churches WHERE country=? AND faith=?", ('TH', 'Jewish'))
bounds = c.fetchone()
print(f'\nCoordinate bounds: lat [{bounds[0]:.3f}, {bounds[1]:.3f}], lon [{bounds[2]:.3f}, {bounds[3]:.3f}]')
print(f'Thailand roughly:   lat [5.6, 20.5], lon [97.3, 105.6]')

# Any coordinates way outside Thailand?
c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND faith=? AND (latitude < 5 OR latitude > 21 OR longitude < 97 OR longitude > 106)", ('TH', 'Jewish'))
outside = c.fetchone()[0]
print(f'Entries with coordinates outside Thailand bounds: {outside}')

# Deep audit: holy_sites_import faith breakdown in TH
c.execute("""
    SELECT faith, COUNT(*) as cnt
    FROM churches
    WHERE country='TH' AND source='holy_sites_import'
    GROUP BY faith
    ORDER BY cnt DESC
""")
print('\nFaith breakdown of TH holy_sites_import entries:')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Global holy_sites_import stats
c.execute("SELECT COUNT(*) FROM churches WHERE source='holy_sites_import'")
total_hs = c.fetchone()[0]
print(f'\nTotal holy_sites_import entries globally: {total_hs}')

c.execute("SELECT COUNT(*) FROM churches WHERE source='holy_sites_import' AND faith='Jewish'")
hs_jewish = c.fetchone()[0]
print(f'holy_sites_import tagged Jewish globally: {hs_jewish}')

c.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches
    WHERE source='holy_sites_import' AND faith='Jewish'
    GROUP BY country ORDER BY cnt DESC
    LIMIT 15
""")
print('\nholy_sites_import Jewish entries by country:')
for r in c.fetchall():
    print(f'  {r[0]}: {r[1]}')

# Real synagogues in TH from other sources
c.execute("SELECT COUNT(*) FROM churches WHERE country='TH' AND faith='Jewish' AND source!='holy_sites_import'")
real = c.fetchone()[0]
print(f'\nNon-holy_sites Jewish entries in TH: {real}')
c.execute("SELECT name,source FROM churches WHERE country='TH' AND faith='Jewish' AND source!='holy_sites_import'")
for r in c.fetchall():
    print(f'  {r[0]} ({r[1]})')

conn.close()

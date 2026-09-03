"""Analyze remaining null-faith entries to guide classifier decisions."""
import sqlite3

conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# What's null-faith by country (top)
c.execute("SELECT country, COUNT(*) FROM churches WHERE faith IS NULL OR faith='' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 25")
print('Null faith by country:')
for r in c.fetchall():
    print(f'  {str(r[0]):4s} {r[1]:>8,}')

# Null faith by landmark_type
c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND landmark_type IS NOT NULL AND landmark_type != '' GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print('\nNull faith by landmark_type:')
for r in c.fetchall():
    print(f'  {str(r[0]):25s} {r[1]:>8,}')

# JP entries with shrine landmark_type
c.execute("SELECT COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND country='JP' AND landmark_type='shrine'")
print(f'\nJP shrines (likely Shinto): {c.fetchone()[0]:,}')

# Already classified Shinto
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Shinto'")
print(f'Already classified Shinto: {c.fetchone()[0]:,}')

# Mosques with null faith
c.execute("SELECT COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND (landmark_type='mosque')")
print(f'Mosques (landmark_type) w/ null faith: {c.fetchone()[0]:,}')

# Non-Christian name patterns remaining
queries = [
    ('Hindu (mandir/ashram)', "name LIKE '%mandir%' OR name LIKE '%ashram%' OR name LIKE '%devi%' OR name LIKE '%shiva%' OR name LIKE '%vishnu%' OR name LIKE '%krishna%'"),
    ('Buddhist (wat/vihara)', "name LIKE '%wat %' OR name LIKE '%vihara%' OR name LIKE '%dharma%' OR name LIKE '%buddha%'"),
    ('Jewish (synagogue)', "name LIKE '%synagogue%'"),
    ('Shinto pattern JP', "country='JP' AND name LIKE '%神社%'"),
    ('Chinese temple TW/CN/HK', "country IN ('TW','CN','HK') AND (name LIKE '%宮%' OR name LIKE '%廟%' OR name LIKE '%寺%' OR name LIKE '%祠%')"),
]
for label, where in queries:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND ({where})")
    print(f'{label}: {c.fetchone()[0]:,}')

conn.close()
print('\nDone.')

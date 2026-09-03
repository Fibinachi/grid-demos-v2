"""Analyze Salvation Army entries in the database."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db')

# Search for Salvation Army in various columns
for col in ['family', 'tradition_legacy', 'subtradition', 'religion_type', 'denomination_affiliation', 'name']:
    cur = db.execute(f'SELECT COUNT(*) FROM churches WHERE {col} LIKE ?', ('%Salvation%',))
    cnt = cur.fetchone()[0]
    print(f'{col}: {cnt} matches')

# Family
print('\nFamily values for SA:')
cur = db.execute('SELECT family, COUNT(*) FROM churches WHERE name LIKE ? OR denomination_affiliation LIKE ? GROUP BY family ORDER BY COUNT(*) DESC',
                 ('%Salvation Army%', '%Salvation Army%'))
for r in cur:
    print(f'  {r[1]:>6} | family={r[0]}')

# Subtradition
print('\nSubtradition values:')
cur = db.execute('SELECT subtradition, COUNT(*) FROM churches WHERE name LIKE ? OR denomination_affiliation LIKE ? GROUP BY subtradition ORDER BY COUNT(*) DESC LIMIT 20',
                 ('%Salvation Army%', '%Salvation Army%'))
for r in cur:
    print(f'  {r[1]:>6} | subtradition={r[0]}')

# Denomination_affiliation
print('\nDenomination_affiliation values:')
cur = db.execute('SELECT denomination_affiliation, COUNT(*) FROM churches WHERE name LIKE ? OR denomination_affiliation LIKE ? GROUP BY denomination_affiliation ORDER BY COUNT(*) DESC LIMIT 30',
                 ('%Salvation Army%', '%Salvation Army%'))
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Religion_type
print('\nReligion_type values:')
cur = db.execute('SELECT religion_type, COUNT(*) FROM churches WHERE name LIKE ? OR denomination_affiliation LIKE ? GROUP BY religion_type ORDER BY COUNT(*) DESC',
                 ('%Salvation Army%', '%Salvation Army%'))
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Top names
print('\nTop 80 name patterns:')
cur = db.execute("SELECT name, COUNT(*) as cnt FROM churches WHERE (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%') AND name IS NOT NULL GROUP BY name ORDER BY cnt DESC LIMIT 80")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Check if there are also entries that might be SA but not labeled as SA
print('\n--- Broader search for potential SA entries ---')
for kw in ['SALVATION ARMY', 'Salvation Army', 'salvation army', 'Salvation Army Temple',
           'Salvation Army Church', 'SA ', 'S.A. Church']:
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ?", (f'%{kw}%',))
    print(f'  {kw}: {cur.fetchone()[0]}')

# Country breakdown
print('\nCountry breakdown:')
cur = db.execute("SELECT country, COUNT(*) FROM churches WHERE (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%') GROUP BY country ORDER BY COUNT(*) DESC LIMIT 30")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Check landmark_type
print('\nLandmark types:')
cur = db.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%') GROUP BY landmark_type ORDER BY COUNT(*) DESC")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Name patterns - show more detail on first 300 entries
print('\n--- Sample entries (first 30) ---')
cur = db.execute("SELECT name, city, state, country, denomination_affiliation, landmark_type FROM churches WHERE (name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%') LIMIT 30")
for r in cur:
    print(f'  {r[0]:55s} | {str(r[1] or ""):20s} | {str(r[2] or ""):10s} | {r[3]:2s} | {str(r[4] or ""):30s} | {r[5]}')

# Total count
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' OR denomination_affiliation LIKE '%Salvation Army%'")
print(f'\nTotal SA entries: {cur.fetchone()[0]}')

# Count entry types beyond just the name
db.close()

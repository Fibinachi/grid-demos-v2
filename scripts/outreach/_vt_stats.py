"""Quick Vermont stats for political data firm pitch."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Vermont overview
print('=== VERMONT CHURCHES OVERVIEW ===')
row = db.execute("SELECT COUNT(*) as cnt FROM churches WHERE state='VT' AND country='US'").fetchone()
print(f'Total VT churches: {row["cnt"]:,}')

# Faith breakdown
print('\n--- Faith Breakdown ---')
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r["faith"]}: {r["n"]:,}')

# Tradition breakdown (top 20)
print('\n--- Top Traditions ---')
for r in db.execute("SELECT tradition, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND tradition IS NOT NULL GROUP BY tradition ORDER BY n DESC LIMIT 20"):
    print(f'  {r["tradition"]}: {r["n"]:,}')

# Contact info
print('\n--- Contact Coverage ---')
for r in db.execute('''
    SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US'
    GROUP BY contact_type
'''):
    print(f'  {r["contact_type"]}: {r["n"]:,}')

# City breakdown
print('\n--- Top Cities ---')
for r in db.execute("SELECT city, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY city ORDER BY n DESC LIMIT 12"):
    print(f'  {r["city"]}: {r["n"]:,}')

# County breakdown
print('\n--- County Breakdown ---')
for r in db.execute("SELECT county, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY county ORDER BY n DESC"):
    print(f'  {r["county"]}: {r["n"]:,}')

# GPS coverage
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()
total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()
print(f'\nGPS coverage: {gps["n"]:,}/{total["n"]:,} ({100*gps["n"]//total["n"]}%)')

# Denomination depth
print('\n--- Denomination Depth (top 20) ---')
for r in db.execute('''
    SELECT denomination, COUNT(*) as n 
    FROM churches 
    WHERE state='VT' AND country='US' AND denomination IS NOT NULL 
    GROUP BY denomination ORDER BY n DESC LIMIT 20
'''):
    print(f'  {r["denomination"]}: {r["n"]:,}')

# Phone numbers available
phones = db.execute('''
    SELECT COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US' AND cv.contact_type='phone'
''').fetchone()
print(f'\nChurches with phone: {phones["n"]:,}')

# Landscape type breakdown
print('\n--- Landmark Types ---')
for r in db.execute("SELECT landmark_type, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY landmark_type ORDER BY n DESC LIMIT 10"):
    print(f'  {r["landmark_type"]}: {r["n"]:,}')

# Enrichment data
print('\n--- Enrichment Coverage ---')
for r in db.execute('''
    SELECT COUNT(DISTINCT ce.church_id) as n
    FROM church_enrichment ce
    JOIN churches c ON c.id = ce.church_id
    WHERE c.state='VT' AND c.country='US'
'''):
    print(f'  Enriched records: {r["n"]:,}')

db.close()

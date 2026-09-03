"""Audit ungeocoded Jewish entries for geocoding feasibility"""
import sqlite3

DB = 'E:/grid/churches.db'
db = sqlite3.connect(DB)
cur = db.cursor()

# 1. Total Jewish without coords
cur.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith = 'Jewish' 
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
""")
total = cur.fetchone()[0]
print(f'Jewish entries without coords: {total:,}')

# 2. Breakdown by source
print()
print('=== Source breakdown (ungeocoded) ===')
cur.execute("""
    SELECT source, COUNT(*) as cnt
    FROM churches
    WHERE faith = 'Jewish'
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
    GROUP BY source
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f'  {str(r[0]):30s} {r[1]:>8,}')

# 3. Breakdown by faith_tradition
print()
print('=== faith_tradition breakdown (ungeocoded) ===')
cur.execute("""
    SELECT faith_tradition, COUNT(*) as cnt
    FROM churches
    WHERE faith = 'Jewish'
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
    GROUP BY faith_tradition
    ORDER BY cnt DESC
""")
for r in cur.fetchall():
    print(f'  {str(r[0]):30s} {r[1]:>8,}')

# 4. Check address availability in churches table
print()
print('=== Address/contact data availability ===')
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN name IS NOT NULL AND name != '' THEN 1 ELSE 0 END) as has_name,
        SUM(CASE WHEN address IS NOT NULL AND address != '' THEN 1 ELSE 0 END) as has_addr,
        SUM(CASE WHEN city IS NOT NULL AND city != '' THEN 1 ELSE 0 END) as has_city,
        SUM(CASE WHEN state IS NOT NULL AND state != '' THEN 1 ELSE 0 END) as has_state,
        SUM(CASE WHEN country IS NOT NULL AND country != '' THEN 1 ELSE 0 END) as has_country,
        SUM(CASE WHEN postal_code IS NOT NULL AND postal_code != '' THEN 1 ELSE 0 END) as has_zip
    FROM churches
    WHERE faith = 'Jewish'
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
""")
r = cur.fetchone()
print(f'  Total ungeocoded:       {r[0]:>8,}')
print(f'  Has name:               {r[1]:>8,}')
print(f'  Has address:            {r[2]:>8,}')
print(f'  Has city:               {r[3]:>8,}')
print(f'  Has state:              {r[4]:>8,}')
print(f'  Has country:            {r[5]:>8,}')
print(f'  Has postal_code:        {r[6]:>8,}')

# 5. Check if any have city in church_contacts
cur.execute("""
    SELECT COUNT(*) 
    FROM churches c
    INNER JOIN church_contacts ct ON ct.church_id = c.rowid
    WHERE c.faith = 'Jewish'
      AND (c.latitude IS NULL OR c.longitude IS NULL OR c.latitude = 0 OR c.longitude = 0)
      AND (ct.city IS NOT NULL AND ct.city != '')
""")
print(f'  Has city in church_contacts: {cur.fetchone()[0]:>8,}')

# 6. Show some sample records
print()
print('=== Sample ungeocoded entries (10) ===')
cur.execute("""
    SELECT rowid, name, faith_tradition, city, state, country, address, source
    FROM churches
    WHERE faith = 'Jewish'
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
    LIMIT 10
""")
for r in cur.fetchall():
    print(f'  rowid={r[0]:>8} | {str(r[1]):40s} | FT={str(r[2]):20s} | city={str(r[3]):20s} | state={str(r[4]):15s} | country={r[5]:5s} | src={r[7]:25s}')

# 7. Country breakdown of ungeocoded
print()
print('=== Country breakdown (ungeocoded, top 20) ===')
cur.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches
    WHERE faith = 'Jewish'
      AND (latitude IS NULL OR longitude IS NULL OR latitude = 0 OR longitude = 0)
      AND country IS NOT NULL AND country != ''
    GROUP BY country
    ORDER BY cnt DESC
    LIMIT 20
""")
for r in cur.fetchall():
    print(f'  {r[0]:5s} {r[1]:>8,}')

db.close()

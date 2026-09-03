"""Analyze Salvation Army territorial/divisional patterns."""
import sqlite3, re

db = sqlite3.connect('E:\\grid\\churches.db')

# Check for territory/division keywords
print('=== Territory/Division/Region keywords ===')
for kw in ['Territor', 'Division', 'Divisional', 'Region', 'Regional',
           'Command', 'Area', 'Province', 'District', 'Zone']:
    cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ? AND name LIKE '%Salvation Army%'", (f'%{kw}%',))
    c = cur.fetchone()[0]
    if c > 0:
        cur2 = db.execute("SELECT name, city, country FROM churches WHERE name LIKE ? AND name LIKE '%Salvation Army%' LIMIT 5", (f'%{kw}%',))
        print(f'\n{kw} ({c} total):')
        for r in cur2:
            print(f'  {r[0]:65s} | {str(r[1] or ""):20s} | {r[2]}')

# Australia-specific
print('\n=== Australia-specific patterns ===')
cur = db.execute("SELECT name, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND country='AU' AND name NOT IN ('Salvation Army', 'SALVATION ARMY') GROUP BY name ORDER BY COUNT(*) DESC LIMIT 30")
for r in cur:
    print(f'  {r[1]:>3} | {r[0]}')

# Canada-specific
print('\n=== Canada-specific patterns ===')
cur = db.execute("SELECT name, city, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND country='CA' AND name NOT LIKE 'GOVERNING COUNCIL%' AND name NOT IN ('Salvation Army', 'SALVATION ARMY') GROUP BY name, city ORDER BY COUNT(*) DESC LIMIT 40")
for r in cur:
    print(f'  {r[2]:>3} | {r[0]:65s} | {str(r[1] or ""):20s}')

# UK-specific
print('\n=== UK-specific patterns ===')
cur = db.execute("SELECT name, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND country='GB' AND name NOT IN ('Salvation Army', 'SALVATION ARMY') AND name NOT LIKE 'GOVERNING COUNCIL%' GROUP BY name ORDER BY COUNT(*) DESC LIMIT 30")
for r in cur:
    print(f'  {r[1]:>3} | {r[0]}')

# US-specific
print('\n=== US-specific patterns ===')
cur = db.execute("SELECT name, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND country='US' AND name NOT IN ('Salvation Army', 'SALVATION ARMY', 'SALVATION ARMY') GROUP BY name ORDER BY COUNT(*) DESC LIMIT 40")
for r in cur:
    print(f'  {r[1]:>3} | {r[0]}')

# Check for entries that have normalized_name set
print('\n=== normalized_name for SA entries ===')
cur = db.execute("SELECT normalized_name, COUNT(*) FROM churches WHERE name LIKE '%Salvation Army%' AND normalized_name IS NOT NULL GROUP BY normalized_name LIMIT 20")
for r in cur:
    print(f'  {r[1]:>3} | {r[0]}')

# Check landmark_type distribution by name pattern  
print('\n=== landmark_type for key patterns ===')
for pattern in ['Corps', 'Citadel', 'Temple', 'Thrift', 'Church', 'Hall', 'Chapel', 'Community']:
    cur = db.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE name LIKE ? AND name LIKE '%Salvation Army%' GROUP BY landmark_type ORDER BY COUNT(*) DESC", (f'%{pattern}%',))
    rows = cur.fetchall()
    if rows:
        print(f'\n{pattern}:')
        for r in rows:
            print(f'  {r[1]:>5} | {r[0]}')

db.close()

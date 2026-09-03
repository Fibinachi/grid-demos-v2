"""Validate Salvation Army hierarchy."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

print('=== sa_hierarchy overview ===')
cnt = db.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]
print(f'Total rows: {cnt}')

# Type breakdown
print('\nType breakdown:')
cur = db.execute("SELECT sa_type, COUNT(*) FROM sa_hierarchy GROUP BY sa_type ORDER BY COUNT(*) DESC")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Hierarchy links
linked = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f'\nLinked entries: {linked}')
cur = db.execute("""
    SELECT c2.sa_type, c1.sa_detail, c1.relationship, c1.notes
    FROM sa_hierarchy c1
    JOIN sa_hierarchy c2 ON c1.parent_id = c2.id
    LIMIT 15
""")
print('Sample links:')
for r in cur:
    print(f'  Child type: {r[0]:20s} | Child: {str(r[1] or "")[:40]:40s} | Rel: {r[2] or "":20s} | {r[3]}')

# Country breakdown
print('\nCountry breakdown:')
cur = db.execute("""
    SELECT country, COUNT(*) FROM sa_hierarchy 
    WHERE country IS NOT NULL AND country != ''
    GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20
""")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

# Check churches update
c = db.execute("SELECT COUNT(*) FROM churches WHERE denomination_affiliation = 'The Salvation Army'").fetchone()[0]
print(f'\nChurches with SA denomination: {c}')
c2 = db.execute("SELECT COUNT(*) FROM churches WHERE family = 'Holiness Churches' AND denomination_affiliation = 'The Salvation Army'").fetchone()[0]
print(f'  of which with Holiness Churches family: {c2}')

# Sample HQ links
print('\n=== HQ entries ==')
cur = db.execute("""
    SELECT name, city, country, sa_detail
    FROM sa_hierarchy WHERE sa_type = 'hq' ORDER BY country
""")
for r in cur:
    print(f'  {r[0]:55s} | {str(r[1] or ""):20s} | {str(r[2] or ""):5s} | {r[3]}')

# Sample corps entries
print('\n=== Sample corps (first 15) ===')
cur = db.execute("SELECT name, city, country, sa_detail FROM sa_hierarchy WHERE sa_type='corps' ORDER BY country, city LIMIT 15")
for r in cur:
    print(f'  {r[0]:55s} | {str(r[1] or ""):20s} | {r[2]:5s} | {r[3]}')

# Top-level entries (no parent)
print('\n=== Orphaned entries by type (no parent) ===')
cur = db.execute("""
    SELECT sa_type, COUNT(*) FROM sa_hierarchy 
    WHERE parent_id IS NULL GROUP BY sa_type ORDER BY COUNT(*) DESC
""")
for r in cur:
    print(f'  {r[1]:>6} | {r[0]}')

db.close()

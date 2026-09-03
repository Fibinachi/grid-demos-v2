"""Check holy_sites_import: how did Buddhist temples become Jewish?"""
import sqlite3

c = sqlite3.connect(r'E:\grid\churches.db')

# 1. Check holy_sites_import entries with faith=Jewish in BR, ST, ID, MY, ST
print("=== ST (São Tomé) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='ST' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

print("\n=== ID (Indonesia) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

print("\n=== BR (Brazil) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='BR' AND source='holy_sites_import'
    LIMIT 20
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

# 2. What is the faith classification mapping for holy_sites_import?
# How was faith=Jewish assigned?
print("\n=== SY (Syria) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='SY' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

# 3. Check IN (India) holy_sites Jewish
print("\n=== IN (India) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='IN' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

# 4. CN (China) holy_sites Jewish
print("\n=== CN (China) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='CN' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

# 5. EG (Egypt) holy_sites Jewish
print("\n=== EG (Egypt) holy_sites Jewish — sample ===")
rows = c.execute("""
    SELECT name, landmark_type, faith_tradition, denomination
    FROM churches 
    WHERE faith='Jewish' AND country='EG' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-50s type=%-12s tradition=%-12s denom=%s' % (r[0][:50] if r[0] else '', r[1] or '', r[2] or '', r[3] or ''))

# 6. SA entries OUTSIDE Israel — what are they?
print("\n=== SA Jewish OUTSIDE Israel — sample ===")
rows = c.execute("""
    SELECT name, latitude, longitude, source
    FROM churches 
    WHERE faith='Jewish' AND country='SA'
      AND (latitude < 29.0 OR latitude > 34.0 OR longitude < 34.0 OR longitude > 37.0)
    LIMIT 20
""").fetchall()
for r in rows:
    print(f'  name=%-55s lat=%8.4f lon=%8.4f source=%s' % (r[0][:55] if r[0] else '', r[1] or 0, r[2] or 0, r[3][:25]))

c.close()

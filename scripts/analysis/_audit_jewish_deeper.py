"""Deeper audit of Jewish misclassifications."""
import sqlite3

c = sqlite3.connect(r'E:\grid\churches.db')

# 1. SA Jewish — check lat/lon range to see if they're actually in Israel
print("=== SA Jewish — lat/lon sample ===")
rows = c.execute("""
    SELECT name, latitude, longitude, source
    FROM churches 
    WHERE faith='Jewish' AND country='SA' 
    ORDER BY RANDOM() 
    LIMIT 10
""").fetchall()
for r in rows:
    print(f'  name=%-55s lat=%8.4f lon=%8.4f source=%s' % (r[0][:55] if r[0] else '', r[1] or 0, r[2] or 0, r[3][:25]))

# Min/max lat/lon for SA Jewish entries
stats = c.execute("""
    SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude), COUNT(*)
    FROM churches WHERE faith='Jewish' AND country='SA'
""").fetchone()
print(f'\n  SA Jewish lat range: {stats[0]:.4f} to {stats[1]:.4f}')
print(f'  SA Jewish lon range: {stats[2]:.4f} to {stats[3]:.4f}')
print(f'  Total: {stats[4]}')

# 2. TH Jewish — these look like Buddhist temples, check actual landmark_type & names
print("\n=== Thailand Jewish — name pattern analysis ===")
rows = c.execute("""
    SELECT name, source, landmark_type, faith_tradition
    FROM churches 
    WHERE faith='Jewish' AND country='TH' 
    ORDER BY RANDOM() 
    LIMIT 30
""").fetchall()
wat_count = 0
for r in rows:
    has_wat = 'วัด' in (r[0] or '')
    print(f'  {"[WAT]" if has_wat else "     "} name=%-55s source=%-30s type=%s' % (r[0][:55] if r[0] else '', r[1][:30] if r[1] else '', r[2] or ''))
    if has_wat:
        wat_count += 1
print(f'\n  Sample with วัด (wat/temple) prefix: {wat_count}/30')

# Check: how many Thai Jewish have Thai Buddhist keywords in name?
cnt = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH'").fetchone()[0]
result = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='TH' AND (name LIKE '%วัด%' OR name LIKE '%ศาล%' OR name LIKE '%สำนัก%')
""").fetchone()[0]
print(f'  Thai Buddhist keywords in names: {result}/{cnt}')

# 3. JO Jewish - same lat/lon issue as SA?
print("\n=== Jordan Jewish — lat/lon sample ===")
rows = c.execute("""
    SELECT name, latitude, longitude, source
    FROM churches 
    WHERE faith='Jewish' AND country='JO' 
    ORDER BY RANDOM() 
    LIMIT 10
""").fetchall()
for r in rows:
    print(f'  name=%-55s lat=%8.4f lon=%8.4f source=%s' % (r[0][:55] if r[0] else '', r[1] or 0, r[2] or 0, r[3][:25]))

stats = c.execute("""
    SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude), COUNT(*)
    FROM churches WHERE faith='Jewish' AND country='JO'
""").fetchone()
print(f'\n  JO Jewish lat range: {stats[0]:.4f} to {stats[1]:.4f}')
print(f'  JO Jewish lon range: {stats[2]:.4f} to {stats[3]:.4f}')

# 4. Check holy_sites_import faith assignment - how did Thai Buddhist temples become Jewish?
print("\n=== TH holy_sites_import: check original landmark/fixed fields ===")
rows = c.execute("""
    SELECT name, landmark_type, landmark, faith_tradition
    FROM churches 
    WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-55s landmark_type=%-12s landmark=%s' % (r[0][:55] if r[0] else '', r[2][:12] if r[2] else 'null', r[3] or ''))

# 5. What about all entries where faith=Jewish AND country NOT in (US, IL, DE, PL, FR, GB, UA, CA)?
print("\n=== Countries with suspicious Jewish entries (non-core countries) ===")
rows = c.execute("""
    SELECT country, COUNT(*) as cnt,
           SUM(CASE WHEN source LIKE '%holy_sites%' THEN 1 ELSE 0 END) as holy_sites,
           SUM(CASE WHEN source LIKE '%osm%' THEN 1 ELSE 0 END) as osm
    FROM churches 
    WHERE faith='Jewish' AND country NOT IN ('US','IL','DE','PL','FR','GB','UA','CA','NL','HU','CZ')
        AND country IS NOT NULL AND country != ''
    GROUP BY country 
    HAVING cnt >= 20
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f'  {r[0]:4s}: {r[1]:>6,} total (holy_sites={r[2]:>6,}, osm={r[3]:>6,})')

# 6. Check: what's the classification pipeline for holy_sites_import?
# Look at how faith was set — was it from the original import or from an enrichment step?
print("\n=== Holy_sites_import Jewish — faith_tradition breakdown ===")
rows = c.execute("""
    SELECT faith_tradition, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Jewish' AND source='holy_sites_import'
    GROUP BY faith_tradition
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f'  {r[0] or "NULL":30s}: {r[1]:>8,}')

# 7. Do Thai Jewish entries have landmark=something that explains the classification?
print("\n=== TH holy_sites landmark values ===")
rows = c.execute("""
    SELECT landmark, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import' AND landmark IS NOT NULL
    GROUP BY landmark
    ORDER BY cnt DESC
    LIMIT 20
""").fetchall()
for r in rows:
    print(f'  {r[0]:30s}: {r[1]:>6,}')

c.close()

"""Quantify all Jewish misclassification issues."""
import sqlite3

c = sqlite3.connect(r'E:\grid\churches.db')

# 1. How many osm_import country code errors?
# SA entries with Israel lat/lon
sa_israel = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='SA' AND source='osm_import'
    AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
""").fetchone()[0]

jo_israel = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='JO' AND source='osm_import'
    AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
""").fetchone()[0]

print('=== Country code error quantification ===')
print(f'  osm_import SA→IL (lat/lon in Israel): {sa_israel:,}')
print(f'  osm_import JO→IL (lat/lon in Israel): {jo_israel:,}')

# Also check PS osm_import - are these also in Israel?
ps_in_israel = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='PS' AND source LIKE '%osm%'
    AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
""").fetchone()[0]
print(f'  osm_import PS (lat/lon in Israel/Palestine): {ps_in_israel:,}')

# 2. Quantify Thailand holy_sites misclassification
th_total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH'").fetchone()[0]
th_wat = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH' AND name LIKE '%วัด%'").fetchone()[0]
th_san = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND country='TH' AND (name LIKE '%ศาล%' OR name LIKE '%สำนัก%' OR name LIKE '%สถูป%')").fetchone()[0]
th_buddhist_kw = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='TH' 
    AND (name LIKE '%วัด%' OR name LIKE '%ศาล%' OR name LIKE '%สำนัก%' OR name LIKE '%สถูป%' OR name LIKE '%กุฏิ%' OR name LIKE '%สวน%')
""").fetchone()[0]

print(f'\n=== Thailand misclassification quantification ===')
print(f'  Total Jewish in Thailand: {th_total}')
print(f'  With วัด (wat/temple): {th_wat}')
print(f'  With other Buddhist keywords: {th_san}')
print(f'  With any Buddhist keyword: {th_buddhist_kw}')
print(f'  Likely Buddhist misclassified: {th_buddhist_kw}/{th_total} ({th_buddhist_kw/th_total*100:.0f}%)')

# 3. What about other countries with holy_sites_import Jewish entries that look misclassified?
print(f'\n=== holy_sites_import Jewish - non-core country breakdown ===')
rows = c.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Jewish' AND source='holy_sites_import' 
      AND country NOT IN ('US','IL','DE','PL','FR','GB','UA','CA','NL','HU','CZ','AT','GR')
    GROUP BY country
    HAVING cnt >= 5
    ORDER BY cnt DESC
""").fetchall()
for r in rows:
    print(f'  {r[0]:4s}: {r[1]:>5,}')

# 4. Check Turkey (TR) - some look reasonable, some might be misclassified
print(f'\n=== Turkey Jewish entries by source ===')
rows = c.execute("SELECT source, COUNT(*) FROM churches WHERE faith='Jewish' AND country='TR' GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
for r in rows:
    print(f'  {r[0]:35s}: {r[1]:>5,}')

# 5. Total misclassification estimate
sa_fixable = sa_israel
jo_fixable = jo_israel
th_fixable = th_buddhist_kw
print(f'\n=== Summary of fixable issues ===')
print(f'  Country code fixes (SA→IL): {sa_fixable:,}')
print(f'  Country code fixes (JO→IL): {jo_fixable:,}')
print(f'  Faith reclassifications (TH Buddhist→Buddhist): {th_fixable:,}')
print(f'  ---')
print(f'  Total entries affected: {sa_fixable + jo_fixable + th_fixable:,}')

# 6. What about the 54 remaining Thai entries without Buddhist keywords?
print(f'\n=== Thailand non-Buddhist-keyword Jewish entries ===')
rows = c.execute("""
    SELECT name, source
    FROM churches 
    WHERE faith='Jewish' AND country='TH'
      AND name NOT LIKE '%วัด%' AND name NOT LIKE '%ศาล%' AND name NOT LIKE '%สำนัก%' AND name NOT LIKE '%สถูป%' AND name NOT LIKE '%กุฏิ%' AND name NOT LIKE '%สวน%'
    ORDER BY RANDOM()
    LIMIT 15
""").fetchall()
for r in rows:
    print(f'  name=%-55s source=%s' % (r[0][:55] if r[0] else '', r[1][:30] if r[1] else ''))

# 7. Check the Saudi entries that DON'T fall in Israel lat/lon range
print(f'\n=== Saudi entries OUTSIDE Israel lat/lon ===')
rows = c.execute("""
    SELECT name, latitude, longitude, source
    FROM churches 
    WHERE faith='Jewish' AND country='SA'
      AND (latitude < 29.0 OR latitude > 34.0 OR longitude < 34.0 OR longitude > 37.0)
    ORDER BY RANDOM()
    LIMIT 10
""").fetchall()
for r in rows:
    print(f'  name=%-55s lat=%8.4f lon=%8.4f source=%s' % (r[0][:55] if r[0] else '', r[1] or 0, r[2] or 0, r[3][:25]))
sa_outside = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='SA'
      AND (latitude < 29.0 OR latitude > 34.0 OR longitude < 34.0 OR longitude > 37.0)
""").fetchone()[0]
print(f'  Total outside Israel range: {sa_outside}')

c.close()

"""
Phase 1: Check what OSM tag data is available from Overture for classification.
Then build the Spanish classifier rule set.
"""
import os, sqlite3
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = ''
from google.cloud import bigquery

client = bigquery.Client(project='american-rel-infra')

# Check Overture schema for religion/denomination tags
print('=== Checking Overture place table for tag data ===')
t = client.get_table('bigquery-public-data.overture_maps.place')

# Look for religion/denomination in category fields
# categories is a RECORD with: primary, alternate, rules
print('categories sub-fields:')
for s in t.schema:
    if s.name == 'categories':
        for sub in s.fields:
            print(f'  categories.{sub.name}: {sub.field_type}')
            if hasattr(sub, 'fields') and sub.fields:
                for sub2 in sub.fields[:8]:
                    print(f'    .{sub2.name}: {sub2.field_type}')

# Check if there are any OSM tags accessible
print('\n=== Sample: Overture churches with brand data ===')
sql = '''
SELECT names.primary as name, 
       brand.names.primary as brand,
       categories.primary as cat,
       categories.alternate as alt_cats
FROM `bigquery-public-data.overture_maps.place`
WHERE categories.primary = 'church_cathedral'
  AND bbox.xmin BETWEEN -118.0 AND -86.0
  AND bbox.ymin BETWEEN 14.0 AND 33.0
  AND brand.names.primary IS NOT NULL
LIMIT 10
'''
try:
    for r in client.query(sql).result():
        alt = str(r.alt_cats)[:80] if r.alt_cats else 'None'
        print(f'  {r.name[:40]:40s}  brand={r.brand or "?":25s}  alt_cats={alt}')
except Exception as e:
    print(f'  Error: {str(e)[:150]}')

# ── Local: what do we have in SQLite for MX churches? ──
print('\n=== SQLite: MX church classification state ===')
conn = sqlite3.connect('churches.db')

# Current classification state
for r in conn.execute("""
    SELECT COALESCE(classification_source,'NULL'), COUNT(*) n 
    FROM churches WHERE country='MX'
    GROUP BY 1 ORDER BY 2 DESC
"""):
    print(f'  {r[0]:30s}: {r[1]:>8,}')

# Current denomination state
for r in conn.execute("""
    SELECT COALESCE(denomination,'NULL'), COUNT(*) n 
    FROM churches WHERE country='MX'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
"""):
    print(f'  {r[0]:40s}: {r[1]:>8,}')

# Current faith_tradition (if it exists)
has_ft = 'faith_tradition' in [c[1] for c in conn.execute('PRAGMA table_info(churches)')]
has_sub = 'subtradition' in [c[1] for c in conn.execute('PRAGMA table_info(churches)')]
has_conf = 'confidence_score' in [c[1] for c in conn.execute('PRAGMA table_info(churches)')]
print(f'\n  faith_tradition column: {has_ft}')
print(f'  subtradition column: {has_sub}')
print(f'  confidence_score column: {has_conf}')

# Check brand data from overture_full churches
brand_count = conn.execute("SELECT COUNT(*) FROM churches WHERE source='overture_full' AND country='MX'").fetchone()[0]
print(f'\n  MX overture_full churches: {brand_count:,}')

conn.close()

"""Comprehensive churches table statistics."""
import sqlite3

conn = sqlite3.connect('file:E:/grid/churches.db?mode=ro', uri=True)
c = conn.cursor()
total = c.execute('SELECT COUNT(*) FROM churches').fetchone()[0]

checks = {
    'Total rows': 'SELECT COUNT(*) FROM churches',
    'With id': 'SELECT COUNT(*) FROM churches WHERE id IS NOT NULL',
    'Geocoded (lat/lon)': 'SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL',
    'Geocode source filled': "SELECT COUNT(*) FROM churches WHERE geocode_source IS NOT NULL AND geocode_source != ''",
    'Address filled': "SELECT COUNT(*) FROM churches WHERE address IS NOT NULL AND address != ''",
    'City filled': "SELECT COUNT(*) FROM churches WHERE city IS NOT NULL AND city != ''",
    'State filled': "SELECT COUNT(*) FROM churches WHERE state IS NOT NULL AND state != ''",
    'ZIP filled': "SELECT COUNT(*) FROM churches WHERE zip IS NOT NULL AND zip != ''",
    'Country filled': "SELECT COUNT(*) FROM churches WHERE country IS NOT NULL AND country != ''",
    'FIPS filled': "SELECT COUNT(*) FROM churches WHERE fips IS NOT NULL AND fips != ''",
    'Normalized name': "SELECT COUNT(*) FROM churches WHERE normalized_name IS NOT NULL AND normalized_name != ''",
    'Faith filled': "SELECT COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != ''",
    'Faith tradition filled': "SELECT COUNT(*) FROM churches WHERE faith_tradition IS NOT NULL AND faith_tradition != ''",
    'Denomination filled': "SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''",
    'Denom affiliation': "SELECT COUNT(*) FROM churches WHERE denomination_affiliation IS NOT NULL AND denomination_affiliation != ''",
    'EIN filled': "SELECT COUNT(*) FROM churches WHERE ein IS NOT NULL AND ein != ''",
    'NTEE code filled': "SELECT COUNT(*) FROM churches WHERE ntee_code IS NOT NULL AND ntee_code != ''",
    'OSM sourced': 'SELECT COUNT(*) FROM churches WHERE osm_id IS NOT NULL',
    'Wikidata sourced': 'SELECT COUNT(*) FROM churches WHERE wikidata_qid IS NOT NULL',
    'Overture sourced': 'SELECT COUNT(*) FROM churches WHERE overture_id IS NOT NULL',
    'CRA sourced (Canada)': 'SELECT COUNT(*) FROM churches WHERE cra_bn IS NOT NULL',
    'Mosque type filled': "SELECT COUNT(*) FROM churches WHERE mosque_type IS NOT NULL AND mosque_type != ''",
    'Canonical status': "SELECT COUNT(*) FROM churches WHERE canonical_status IS NOT NULL AND canonical_status != ''",
    'Confidence scored': 'SELECT COUNT(*) FROM churches WHERE confidence_score IS NOT NULL',
    'Building year': 'SELECT COUNT(*) FROM churches WHERE building_year IS NOT NULL',
    'Capacity/area data': 'SELECT COUNT(*) FROM churches WHERE capacity IS NOT NULL OR area_m2 IS NOT NULL',
    'Heritage status': "SELECT COUNT(*) FROM churches WHERE heritage_status IS NOT NULL AND heritage_status != ''",
    'Landmark type': "SELECT COUNT(*) FROM churches WHERE landmark_type IS NOT NULL AND landmark_type != ''",
}

print(f'=== CHURCHES TABLE STATS ({total:,} total) ===')
print()

for label, sql in checks.items():
    try:
        val = c.execute(sql).fetchone()[0]
        pct = (val / total * 100) if total > 0 else 0
        print(f'  {label:<30s} {val:>10,}  ({pct:.1f}%)')
    except Exception as e:
        print(f'  {label:<30s} {"ERR":>10}  {str(e)[:60]}')

print()
print('=== FAITH DISTRIBUTION ===')
for row in c.execute('SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC LIMIT 12'):
    pct = row[1]/total*100
    label = row[0] if row[0] else '(null)'
    print(f'  {label:<30s} {row[1]:>10,}  ({pct:.1f}%)')

print()
print('=== COUNTRY DISTRIBUTION (top 15) ===')
for row in c.execute("SELECT country, COUNT(*) FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15"):
    pct = row[1]/total*100
    print(f'  {row[0]:<30s} {row[1]:>10,}  ({pct:.1f}%)')

print()
print('=== SOURCE DISTRIBUTION (top 12) ===')
for row in c.execute('SELECT source, COUNT(*) FROM churches GROUP BY source ORDER BY COUNT(*) DESC LIMIT 12'):
    pct = row[1]/total*100
    src = (row[0] or '(null)')[:60]
    print(f'  {src:<60s} {row[1]:>10,}  ({pct:.1f}%)')

print()
print('=== TOP DENOMINATIONS (top 15) ===')
for row in c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != '' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15"):
    pct = row[1]/total*100
    print(f'  {row[0][:45]:<45s} {row[1]:>10,}  ({pct:.1f}%)')

conn.close()

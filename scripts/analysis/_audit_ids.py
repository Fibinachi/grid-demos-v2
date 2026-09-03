"""Audit osm_id and wikidata_qid population in holy_sites"""
import sqlite3
db = sqlite3.connect('churches.db')

print('=== osm_id values by source_primary ===')
sql = """SELECT source_primary, COUNT(*) as cnt,
    SUM(CASE WHEN osm_id IS NULL OR osm_id = '' THEN 1 ELSE 0 END) as null_cnt,
    SUM(CASE WHEN osm_id IS NOT NULL AND osm_id != '' THEN 1 ELSE 0 END) as has_id
    FROM holy_sites GROUP BY source_primary ORDER BY cnt DESC LIMIT 15"""
for row in db.execute(sql):
    print(f'{str(row[0]):25s} | total={row[1]:>10,} | null={row[2]:>10,} | has_id={row[3]:>10,}')

print()
print('=== Sample overture osm_id values ===')
for row in db.execute("SELECT osm_id, name, country FROM holy_sites WHERE source_primary='overture' AND osm_id IS NOT NULL AND osm_id != '' LIMIT 10"):
    print(f'  osm_id={str(row[0])[:60]} | name={str(row[1])[:40]} | country={row[2]}')

print()
print('=== wikidata_qid values by source_primary ===')
sql = """SELECT source_primary, COUNT(*) as cnt,
    SUM(CASE WHEN wikidata_qid IS NULL OR wikidata_qid = '' THEN 1 ELSE 0 END) as null_cnt,
    SUM(CASE WHEN wikidata_qid IS NOT NULL AND wikidata_qid != '' THEN 1 ELSE 0 END) as has_qid
    FROM holy_sites GROUP BY source_primary ORDER BY cnt DESC LIMIT 15"""
for row in db.execute(sql):
    print(f'{str(row[0]):25s} | total={row[1]:>10,} | null_qid={row[2]:>10,} | has_qid={row[3]:>10,}')

print()
print('=== Column list for holy_sites ===')
for row in db.execute('PRAGMA table_info(holy_sites)'):
    print(f'  {row[1]:35s} {row[2]}')

print()
print('=== churches table osm/wiki columns? ===')
church_cols = [r[1] for r in db.execute('PRAGMA table_info(churches)')]
for c in ['osm_id', 'osm_type', 'osm_version', 'osm_timestamp', 'wikidata_qid', 'wikidata_last_modified', 'overture_id']:
    print(f'  churches.{c}: {"YES" if c in church_cols else "NO"}')

hs_cols = [r[1] for r in db.execute('PRAGMA table_info(holy_sites)')]
for c in ['osm_id', 'osm_type', 'osm_version', 'osm_timestamp', 'wikidata_qid', 'wikidata_last_modified', 'overture_id']:
    print(f'  holy_sites.{c}: {"YES" if c in hs_cols else "NO"}')

db.close()

"""Rebuild sa_hierarchy with ALL SA entries (name + denomination fields)."""
import sqlite3, sys

sys.path.insert(0, 'e:\\grid\\scripts\\db_maintenance')
from standardize_salvation_army import classify_sa_name, CHUNK, TYPE_ORDER
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')
db.execute('PRAGMA journal_mode=WAL')

# Comprehensive search — name patterns AND denomination fields
print("Searching for all SA entries...")
cur = db.execute("""
    SELECT id, name, city, state, country, latitude, longitude
    FROM churches
    WHERE name LIKE '%Salvation Army%'
       OR name LIKE '%Arm\u00e9e du Salut%'
       OR name LIKE '%Heilsarmee%'
       OR name LIKE '%Frelsesarmeen%'
       OR name LIKE '%Pelastusarmeija%'
       OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
       OR name LIKE '%Ejercito de Salvacion%'
       OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%'
       OR name LIKE '%Exercito de Salvacao%'
       OR name LIKE '%Armia Zbawienia%'
       OR name LIKE '%Fr\u00e4lsningsarm\u00e9n%'
       OR name LIKE '%Fralsningsarmen%'
       OR denomination_affiliation LIKE '%Salvation Army%'
       OR subtradition LIKE '%Salvation%'
    ORDER BY id
""")
rows = cur.fetchall()
print(f'Found {len(rows)} entries')

# Create table fresh
db.execute('DROP TABLE IF EXISTS sa_hierarchy')
db.execute("""
    CREATE TABLE sa_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES sa_hierarchy(id),
        church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        original_name TEXT,
        sa_type TEXT NOT NULL,
        sa_detail TEXT,
        territory TEXT,
        division TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        parent_sa_type TEXT,
        relationship TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
db.execute('CREATE INDEX IF NOT EXISTS idx_sa_type ON sa_hierarchy(sa_type)')
db.execute('CREATE INDEX IF NOT EXISTS idx_sa_country ON sa_hierarchy(country)')
db.execute('CREATE INDEX IF NOT EXISTS idx_sa_church ON sa_hierarchy(church_id)')
db.execute('CREATE INDEX IF NOT EXISTS idx_sa_parent ON sa_hierarchy(parent_id)')

# Classify and insert
batch = []
type_counts = {}
insert_sql = """INSERT INTO sa_hierarchy 
    (church_id, name, original_name, sa_type, sa_detail, city, state, country, lat, lon) 
    VALUES (?,?,?,?,?,?,?,?,?,?)"""

for i, r in enumerate(rows):
    sa_type, detail, normalized, _ = classify_sa_name(r[1] or '', r[2] or '', r[4] or '')
    type_counts[sa_type] = type_counts.get(sa_type, 0) + 1
    batch.append((r[0], normalized, r[1], sa_type, detail, r[2] or '', r[3] or '', r[4] or '', r[5], r[6]))
    if len(batch) >= CHUNK:
        db.executemany(insert_sql, batch)
        db.commit()
        batch = []
    # Progress
    if (i + 1) % 500 == 0 or i == len(rows) - 1:
        pct = (i + 1) * 100 // len(rows)
        print(f'  Classifying: {pct}% ({i+1}/{len(rows)})')

if batch:
    db.executemany(insert_sql, batch)
    db.commit()

cnt = db.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]
print(f'\nInserted {cnt} rows')

# Type breakdown
print('\nType breakdown:')
for t in sorted(type_counts, key=lambda x: -type_counts[x]):
    print(f'  {type_counts[t]:>6} | {t}')

# Build hierarchy links
print('\nBuilding hierarchy links...')
hq_rows = db.execute("""
    SELECT id, church_id, city, state, country, sa_detail
    FROM sa_hierarchy WHERE sa_type = 'hq'
""").fetchall()

link_count = 0
for hq in hq_rows:
    hq_id = hq[0]
    hq_country = hq[4]
    hq_city = (hq[2] or '').lower()
    hq_detail = (hq[5] or '').lower()
    
    subordinate_types = ('corps', 'citadel', 'temple', 'hall', 'chapel',
                        'church', 'community_church', 'generic')
    
    # Link by same city+country
    if hq_city:
        subs = db.execute("""
            SELECT id FROM sa_hierarchy
            WHERE sa_type IN ({})
              AND country = ?
              AND LOWER(city) = ?
              AND parent_id IS NULL
              AND id != ?
        """.format(','.join('?' * len(subordinate_types))),
            subordinate_types + (hq_country, hq_city, hq_id)
        ).fetchall()
        for s in subs:
            db.execute("""UPDATE sa_hierarchy SET parent_id=?, parent_sa_type='hq',
                relationship='part_of', notes='Auto-linked by same city+country'
                WHERE id=?""", (hq_id, s[0]))
            link_count += 1
    
    # Territorial HQs link all in country
    if 'territor' in hq_detail or 'territorial' in hq_detail:
        subs = db.execute("""SELECT id FROM sa_hierarchy 
            WHERE country=? AND id!=? AND parent_id IS NULL""", (hq_country, hq_id)).fetchall()
        for s in subs:
            db.execute("""UPDATE sa_hierarchy SET parent_id=?, parent_sa_type='hq',
                relationship='belongs_to_territory',
                notes='Auto-linked by country to territorial HQ'
                WHERE id=?""", (hq_id, s[0]))
            link_count += 1

db.commit()
print(f'{link_count} hierarchy links created')

# Update churches table
print('\nUpdating churches table...')
church_ids = [r[0] for r in rows]
for i in range(0, len(church_ids), CHUNK):
    batch_ids = church_ids[i:i + CHUNK]
    placeholders = ','.join(['?'] * len(batch_ids))
    db.execute(f"""
        UPDATE churches
        SET denomination_affiliation = 'The Salvation Army',
            family = CASE WHEN family IS NULL THEN 'Holiness Churches' ELSE family END,
            subtradition = CASE WHEN subtradition IS NULL THEN 'Salvationist' ELSE subtradition END
        WHERE id IN ({placeholders})
    """, batch_ids)
    db.commit()
    pct = min(100, (i + len(batch_ids)) * 100 // len(church_ids))
    print(f'  {pct}% ({i + len(batch_ids)}/{len(church_ids)})')

# Log provenance
print('\nLogging provenance...')
now = datetime.now().isoformat()
prov_batch = []
for i, r in enumerate(rows):
    church_id = r[0]
    sa_type = None
    for t in type_counts:
        pass
    # Find the classification for this church
    # Re-classify to get the type
    sa_type, detail, normalized, _ = classify_sa_name(r[1] or '', r[2] or '', r[4] or '')
    prov_batch.append((church_id, 'sa_hierarchy_import', 'classified', now,
                       f'Type={sa_type}, Detail={detail}, Normalized={normalized}'))
    if len(prov_batch) >= CHUNK:
        db.executemany("""
            INSERT INTO provenance_log (church_id, source, action, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """, prov_batch)
        db.commit()
        prov_batch = []
if prov_batch:
    db.executemany("""
        INSERT INTO provenance_log (church_id, source, action, timestamp, details)
        VALUES (?, ?, ?, ?, ?)
    """, prov_batch)
    db.commit()

prov_cnt = db.execute("SELECT COUNT(*) FROM provenance_log WHERE source='sa_hierarchy_import'").fetchone()[0]
print(f'{prov_cnt} provenance entries logged')

# Summary
linked = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
updated = db.execute("SELECT COUNT(*) FROM churches WHERE denomination_affiliation='The Salvation Army'").fetchone()[0]

print(f'\n{"="*50}')
print('SUMMARY')
print(f'{"="*50}')
print(f'Total in sa_hierarchy: {cnt}')
for t in sorted(type_counts, key=lambda x: -type_counts[x]):
    print(f'  {type_counts[t]:>6} | {t}')
print(f'Hierarchy links: {linked}')
print(f'Churches updated with SA denom: {updated}')
print(f'Provenance entries: {prov_cnt}')
print('Done!')
db.close()

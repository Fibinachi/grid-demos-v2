"""
Build catholic_hierarchy table (FTLD already backfilled).
Hierarchy: Parish -> Diocese -> Archdiocese -> Province -> Holy See
"""
import sqlite3
from datetime import datetime

CHUNK = 2000
db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA cache_size=-64000')
db.execute('PRAGMA temp_store=MEMORY')

now = datetime.now().isoformat()

# ═════════════════════════════════════════════════
# Load territories into memory (fits in 32GB RAM)
# ═════════════════════════════════════════════════
print('Loading ecclesiastical territories...')
territories = {}
cur = db.execute("""
    SELECT id, name, full_name, dio_type, dio_type_label, 
           metro_key, country_key, rite_key, rite_label
    FROM ecclesiastical_territories
""")
for r in cur.fetchall():
    territories[r[1].lower()] = {
        'id': r[0], 'name': r[1], 'full_name': r[2],
        'type': r[3], 'type_label': r[4],
        'metro_key': r[5], 'country': r[6],
        'rite': r[7], 'rite_label': r[8]
    }
print(f'  {len(territories)} territories loaded')

# ═════════════════════════════════════════════════
# Create catholic_hierarchy table
# ═════════════════════════════════════════════════
print('Creating catholic_hierarchy table...')
db.execute('DROP TABLE IF EXISTS catholic_hierarchy')
db.execute("""
    CREATE TABLE catholic_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES catholic_hierarchy(id),
        church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        original_name TEXT,
        cath_type TEXT NOT NULL,
        cath_detail TEXT,
        diocese TEXT,
        archdiocese TEXT,
        province TEXT,
        rite TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        parent_cath_type TEXT,
        relationship TEXT,
        territory_id INTEGER,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
indexes = {
    'idx_cath_type': 'cath_type',
    'idx_cath_diocese': 'diocese',
    'idx_cath_church': 'church_id',
    'idx_cath_parent': 'parent_id'
}
for idx_name, idx_col in indexes.items():
    db.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON catholic_hierarchy({idx_col})')
print('  Table created')

# ═════════════════════════════════════════════════
# Insert Holy See
# ═════════════════════════════════════════════════
hs = db.execute("""
    SELECT id, name, city, country, latitude, longitude
    FROM churches
    WHERE country = 'VA' AND (name LIKE '%Holy See%' OR name LIKE '%Vatican%')
    LIMIT 1
""").fetchone()
if hs:
    db.execute("""INSERT INTO catholic_hierarchy 
        (church_id, name, cath_type, cath_detail, city, country, lat, lon)
        VALUES (?, ?, 'holy_see', 'Holy See', ?, ?, ?, ?)""", hs)
else:
    db.execute("""INSERT INTO catholic_hierarchy 
        (name, cath_type, cath_detail, country)
        VALUES ('Holy See — Vatican City', 'holy_see', 'Holy See', 'VA')""")
holy_see_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
db.commit()
print(f'  Holy See: id={holy_see_id}')

# ═════════════════════════════════════════════════
# Insert all dioceses/archdioceses from territories
# ═════════════════════════════════════════════════
print(f'Inserting {len(territories)} territories...')
type_map = {'d': 'diocese', 'a': 'archdiocese', 't': 'diocese',
            'p': 'diocese', 'e': 'diocese', 'ar': 'archdiocese',
            'o': 'other', 'm': 'diocese', 'l': 'diocese'}

territory_id_map = {}
territory_hierarchy = {}
batch = []

for name, t in territories.items():
    t_type = type_map.get(t['type'], 'diocese')
    if t['type'] in ('a', 'ar'):
        t_type = 'archdiocese'
    
    province_name = None
    if t['metro_key'] and t['metro_key'] in territories:
        province_name = territories[t['metro_key']]['full_name']
    
    batch.append((t['full_name'], t_type, t['name'], province_name, 
                  t['country'], t['rite_label'], t['id']))
    territory_id_map[name] = t['id']
    
    if len(batch) >= CHUNK:
        db.executemany("""INSERT INTO catholic_hierarchy 
            (name, cath_type, cath_detail, province, country, rite, territory_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", batch)
        db.commit()
        batch = []

if batch:
    db.executemany("""INSERT INTO catholic_hierarchy 
        (name, cath_type, cath_detail, province, country, rite, territory_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)""", batch)
    db.commit()

# Map territory_id to hierarchy id
for r in db.execute("SELECT id, territory_id, cath_type FROM catholic_hierarchy WHERE territory_id IS NOT NULL").fetchall():
    territory_hierarchy[r[1]] = {'id': r[0], 'type': r[2]}
print(f'  {len(territory_hierarchy)} territories in hierarchy')

# ═════════════════════════════════════════════════
# Link suffragan dioceses to archdioceses via metro_key
# ═════════════════════════════════════════════════
print('Linking suffragan dioceses...')
link_count = 0
for name, t in territories.items():
    t_id = territory_id_map.get(name)
    h = territory_hierarchy.get(t_id) if t_id else None
    if not h or not t['metro_key']:
        continue
    
    metro = t['metro_key']
    metro_t_id = territory_id_map.get(metro)
    metro_h = territory_hierarchy.get(metro_t_id) if metro_t_id else None
    if not metro_h or t['type'] not in ('d', 'e', 'p', 't', 'm', 'l'):
        continue
    
    db.execute("""UPDATE catholic_hierarchy 
        SET parent_id=?, parent_cath_type='archdiocese',
            relationship='suffragan_of',
            archdiocese=(SELECT name FROM catholic_hierarchy WHERE id=?),
            province=(SELECT province FROM catholic_hierarchy WHERE id=?)
        WHERE id=?""", (metro_h['id'], metro_h['id'], metro_h['id'], h['id']))
    link_count += 1

db.commit()
print(f'  {link_count} suffragan links')

# ═════════════════════════════════════════════════
# Create province entries and link archdioceses
# ═════════════════════════════════════════════════
print('Creating provinces...')
prov_count = 0
for name, t in territories.items():
    if t['type'] not in ('a', 'ar'):
        continue
    metro_t_id = territory_id_map.get(name)
    metro_h = territory_hierarchy.get(metro_t_id) if metro_t_id else None
    if not metro_h or not t['metro_key']:
        continue
    
    province_name = f"Province of {t['name']}"
    db.execute("""INSERT INTO catholic_hierarchy 
        (name, cath_type, cath_detail, country, parent_id, parent_cath_type, relationship)
        VALUES (?, 'province', ?, ?, ?, 'holy_see', 'part_of_conference')""",
        (province_name, f"Metropolitan province of {t['full_name']}", t['country'], holy_see_id))
    prov_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    db.execute("""UPDATE catholic_hierarchy 
        SET parent_id=?, parent_cath_type='province',
            relationship='belongs_to_province', province=?
        WHERE id=?""", (prov_id, province_name, metro_h['id']))
    prov_count += 1

db.commit()
print(f'  {prov_count} provinces created')

# ═════════════════════════════════════════════════
# Link parishes via church_enrichment.diocese
# ═════════════════════════════════════════════════
print('Loading parish->diocese links and church data into memory...')
parish_links = dict(db.execute(
    "SELECT church_id, diocese FROM church_enrichment WHERE diocese IS NOT NULL AND diocese != ''"
).fetchall())
print(f'  {len(parish_links):,} links loaded')

# Batch-load ALL Catholic church data into memory (fits in 32GB)
catholic_ids = set(r[0] for r in db.execute(
    "SELECT id FROM churches WHERE legacy='Catholic'"
).fetchall())
print(f'  {len(catholic_ids):,} Catholic church IDs loaded')

church_data = {}
cur = db.execute("SELECT id, name, city, state, country, latitude, longitude, landmark_type FROM churches WHERE legacy='Catholic'")
for r in cur.fetchall():
    church_data[r[0]] = {
        'name': r[1], 'city': r[2], 'state': r[3], 'country': r[4],
        'lat': r[5], 'lon': r[6], 'landmark': r[7]
    }
print(f'  {len(church_data):,} church records loaded')

# Build diocese name -> territory ID lookup
dio_to_territory = {}
for name, t in territories.items():
    t_id = territory_id_map.get(name)
    h = territory_hierarchy.get(t_id) if t_id else None
    if h:
        n = name.replace('-', ' ').replace('_', ' ')
        dio_to_territory[n] = h['id']
        dio_to_territory[t['full_name'].lower().replace('-', ' ').replace('_', ' ')] = h['id']
print(f'  {len(dio_to_territory):,} diocese->territory mappings')

print('Linking parishes...')
parish_batch = []
linked = 0
for church_id, diocese_name in parish_links.items():
    if church_id not in catholic_ids or church_id not in church_data:
        continue
    
    ch = church_data[church_id]
    dio_lower = diocese_name.lower().strip().replace('-', ' ').replace('_', ' ')
    parent_id = dio_to_territory.get(dio_lower)
    
    if not parent_id:
        for key, pid in dio_to_territory.items():
            k = key.lower().replace('-', ' ').replace('_', ' ')
            if dio_lower.startswith(k) or k.startswith(dio_lower):
                parent_id = pid
                break
    
    parish_batch.append((
        church_id, ch['name'], diocese_name,
        ch['city'], ch['state'], ch['country'], ch['lat'], ch['lon'],
        parent_id, 'diocese' if parent_id else None,
        'belongs_to_diocese' if parent_id else None
    ))
    
    if len(parish_batch) >= CHUNK:
        db.executemany("""INSERT INTO catholic_hierarchy 
            (church_id, name, cath_type, cath_detail, city, state, country, lat, lon,
             parent_id, parent_cath_type, relationship)
            VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, ?, ?, ?)""", parish_batch)
        db.commit()
        linked += len(parish_batch)
        parish_batch = []
    
    if linked > 0 and linked % 10000 == 0:
        print(f'    {linked} parishes linked')

if parish_batch:
    db.executemany("""INSERT INTO catholic_hierarchy 
        (church_id, name, cath_type, cath_detail, city, state, country, lat, lon,
         parent_id, parent_cath_type, relationship)
        VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, ?, ?, ?)""", parish_batch)
    db.commit()
    linked += len(parish_batch)

print(f'  Total parishes linked: {linked:,}')

# ═════════════════════════════════════════════════
# Insert remaining Catholic churches as parishes
# ═════════════════════════════════════════════════
inserted = set(r[0] for r in db.execute(
    "SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL"
).fetchall() if r[0])

remaining = catholic_ids - inserted
print(f'Inserting {len(remaining):,} remaining Catholic churches...')

rem_batch = []
for i, cid in enumerate(remaining):
    ch = church_data.get(cid)
    if not ch:
        continue
    
    lm = (ch['landmark'] or '').lower()
    if lm == 'cathedral' or ('cathedral' in (ch['name'] or '').lower() and lm in ('church', '')):
        ctype = 'cathedral'
    elif lm == 'chapel':
        ctype = 'parish'
    elif lm == 'shrine':
        ctype = 'shrine'
    elif lm == 'basilica':
        ctype = 'basilica'
    else:
        ctype = 'parish'
    
    rem_batch.append((cid, ch['name'], ctype, ch['city'], ch['state'], ch['country'], ch['lat'], ch['lon']))
    
    if len(rem_batch) >= CHUNK:
        db.executemany("""INSERT INTO catholic_hierarchy 
            (church_id, name, cath_type, city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rem_batch)
        db.commit()
        rem_batch = []
    
    if (i+1) % 20000 == 0:
        print(f'    {i+1}/{len(remaining)}')

if rem_batch:
    db.executemany("""INSERT INTO catholic_hierarchy 
        (church_id, name, cath_type, city, state, country, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", rem_batch)
    db.commit()

# ═════════════════════════════════════════════════
# Final verification
# ═════════════════════════════════════════════════
print('\n' + '='*60)
print('VERIFICATION')
print('='*60)

total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy").fetchone()[0]
print(f'catholic_hierarchy: {total:,} rows')

print('\nType breakdown:')
for r in db.execute("SELECT cath_type, COUNT(*) FROM catholic_hierarchy GROUP BY cath_type ORDER BY COUNT(*) DESC"):
    print(f'  {r[1]:>8,} | {r[0]}')

linked = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f'\nLinked: {linked:,}')
print(f'Top-level: {total - linked:,}')

# Count distinct levels from root
print('\nDepth distribution:')
for r in db.execute("""
    WITH RECURSIVE depth AS (
        SELECT id, 0 AS lvl FROM catholic_hierarchy WHERE parent_id IS NULL
        UNION ALL
        SELECT ch.id, d.lvl+1 FROM catholic_hierarchy ch JOIN depth d ON ch.parent_id = d.id
    )
    SELECT lvl, COUNT(*) FROM depth GROUP BY lvl ORDER BY lvl
"""):
    print(f'  Level {r[0]}: {r[1]:,}')

# Log provenance
now = datetime.now().isoformat()
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at,
     churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('catholic_hierarchy', '_build_catholic_hierarchy2.py', now, now,
     total, 'catholic_hierarchy', 'completed',
     f'{total} rows, {linked} linked'))
db.commit()

print('\nDone!')
db.close()

"""
Catholic Hierarchy Builder + FTLD backfill.
Uses 32GB RAM efficiently — loads reference data in memory, batch-writes.

Hierarchy: Parish -> Diocese -> Archdiocese -> Province -> Conference -> Holy See

Sources:
  - church_enrichment.diocese: 39K parish->diocese links
  - ecclesiastical_territories: 2,838 territories with metro_key (province links)
  - churches: 145K Catholic entries with GPS/city/country
"""
import sqlite3, sys, re
from datetime import datetime

CHUNK = 2000
db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA cache_size=-64000')  # 64MB cache
db.execute('PRAGMA temp_store=MEMORY')

now = datetime.now().isoformat()

# ═══════════════════════════════════════════════════════════════
# STEP 1: Identify ALL Catholic entries
# ═══════════════════════════════════════════════════════════════
print('=== STEP 1: Identifying Catholic entries ===')
catholic_ids = set(r[0] for r in db.execute("""
    SELECT id FROM churches
    WHERE legacy = 'Catholic'
       OR tradition LIKE '%Catholic%'
    ORDER BY id
""").fetchall())
total = len(catholic_ids)
print(f'  {total:,} Catholic entries identified')

# ═══════════════════════════════════════════════════════════════
# STEP 2: Backfill FTLD (Faith-Tradition-Legacy-Denomination)
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 2: Backfilling FTLD ===')

# Phase 2a: Set faith=christian where missing
to_fix_faith = db.execute(f"""
    SELECT COUNT(*) FROM churches
    WHERE id IN ({','.join('?'*len(catholic_ids))})
      AND (faith IS NULL OR faith = '' OR faith != 'christian')
""", list(catholic_ids)).fetchone()[0]

if to_fix_faith:
    db.execute(f"""
        UPDATE churches SET faith = 'christian'
        WHERE id IN ({','.join('?'*len(catholic_ids))})
          AND (faith IS NULL OR faith = '' OR faith != 'christian')
    """, list(catholic_ids))
    db.commit()
    changed = db.execute("SELECT changes()").fetchone()[0]
    print(f'  faith=christian: {changed} updated')

# Phase 2b: Set legacy=Catholic where missing
to_fix_legacy = db.execute(f"""
    SELECT COUNT(*) FROM churches
    WHERE id IN ({','.join('?'*len(catholic_ids))})
      AND (legacy IS NULL OR legacy = '' OR legacy != 'Catholic')
""", list(catholic_ids)).fetchone()[0]

if to_fix_legacy:
    db.execute(f"""
        UPDATE churches SET legacy = 'Catholic'
        WHERE id IN ({','.join('?'*len(catholic_ids))})
          AND (legacy IS NULL OR legacy = '' OR legacy != 'Catholic')
    """, list(catholic_ids))
    db.commit()
    changed = db.execute("SELECT changes()").fetchone()[0]
    print(f'  legacy=Catholic: {changed} updated')

# Phase 2c: Set tradition=Catholic Churches where missing
to_fix_trad = db.execute(f"""
    SELECT COUNT(*) FROM churches
    WHERE id IN ({','.join('?'*len(catholic_ids))})
      AND (tradition IS NULL OR tradition = '')
""", list(catholic_ids)).fetchone()[0]

if to_fix_trad:
    db.execute(f"""
        UPDATE churches SET tradition = 'Catholic Churches'
        WHERE id IN ({','.join('?'*len(catholic_ids))})
          AND (tradition IS NULL OR tradition = '')
    """, list(catholic_ids))
    db.commit()
    changed = db.execute("SELECT changes()").fetchone()[0]
    print(f'  tradition=Catholic Churches: {changed} updated')

# Phase 2d: Set denomination for Latin-rite Catholic where meaningful
# (Only where denomination is empty and it's clearly a parish church)
db.execute(f"""
    UPDATE churches SET denomination = 'Roman Catholic'
    WHERE id IN ({','.join('?'*len(catholic_ids))})
      AND (denomination IS NULL OR denomination = '')
      AND landmark_type IN ('church', 'chapel', 'basilica', 'cathedral')
      AND (name LIKE 'St%' OR name LIKE 'Our Lady%' OR name LIKE 'San%' 
           OR name LIKE 'Santa%' OR name LIKE 'Santo%' OR name LIKE 'S%C3%A3o%'
           OR name LIKE 'Saint%' OR name LIKE 'Sainte%' OR name LIKE 'Holy%'
           OR name LIKE 'Church of%' OR name LIKE 'Iglesia de%' OR name LIKE 'Chiesa di%'
           OR name LIKE '%Church%' OR name LIKE '%Chapel%')
""", list(catholic_ids))
db.commit()
denom_set = db.execute("SELECT changes()").fetchone()[0]
print(f'  denomination=Roman Catholic: {denom_set} updated')

# Verify
print('\nFTLD after backfill:')
for col, val in [('faith', 'christian'), ('legacy', 'Catholic'), 
                 ('tradition', 'Catholic Churches')]:
    params = list(catholic_ids) + [val]
    c = db.execute(f"SELECT COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(catholic_ids))}) AND {col}=?", params).fetchone()[0]
    print(f'  {col}={val}: {c:,}')

# Log provenance for FTLD
db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ('catholic_ftld', '_build_catholic_hierarchy.py', now, now,
      total, 'faith,legacy,tradition,denomination', 'completed',
      f'Backfilled FTLD for {total} Catholic entries'))
db.commit()

# ═══════════════════════════════════════════════════════════════
# STEP 3: Load ecclesiastical territories into memory
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 3: Loading ecclesiastical territories ===')
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

# Build province map: metro_key -> list of suffragan dioceses
provinces = {}
for name, t in territories.items():
    mk = t['metro_key']
    if mk:
        if mk not in provinces:
            provinces[mk] = []
        provinces[mk].append(t)
print(f'  {len(provinces)} provinces identified')

# ═══════════════════════════════════════════════════════════════
# STEP 4: Create catholic_hierarchy table
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 4: Creating catholic_hierarchy table ===')
db.execute('DROP TABLE IF EXISTS catholic_hierarchy')
db.execute("""
    CREATE TABLE catholic_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES catholic_hierarchy(id),
        church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        original_name TEXT,
        cath_type TEXT NOT NULL CHECK(cath_type IN (
            'parish', 'shrine', 'basilica', 'cathedral',
            'deanery', 'diocese', 'archdiocese', 'province',
            'metropolitan', 'episcopal_conference', 'holy_see',
            'rite', 'religious_order', 'other'
        )),
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
        relationship TEXT CHECK(relationship IN (
            'belongs_to_diocese',
            'belongs_to_archdiocese',
            'belongs_to_province',
            'suffragan_of',
            'part_of_conference',
            'part_of_rite',
            'sees_in'
        )),
        territory_id INTEGER,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
db.execute('CREATE INDEX IF NOT EXISTS idx_cath_type ON catholic_hierarchy(cath_type)')
db.execute('CREATE INDEX IF NOT EXISTS idx_cath_diocese ON catholic_hierarchy(diocese)')
db.execute('CREATE INDEX IF NOT EXISTS idx_cath_church ON catholic_hierarchy(church_id)')
db.execute('CREATE INDEX IF NOT EXISTS idx_cath_parent ON catholic_hierarchy(parent_id)')
print('  Table created')

# ═══════════════════════════════════════════════════════════════
# STEP 5: Insert Holy See (top of pyramid)
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 5: Inserting hierarchy levels ===')

holy_see_id = None
# Find Holy See entry in churches (Vatican City)
hs = db.execute("""
    SELECT id, name, city, country, latitude, longitude
    FROM churches
    WHERE (name LIKE '%Holy See%' OR name LIKE '%Vatican%')
      AND country = 'VA'
    LIMIT 1
""").fetchone()
if hs:
    db.execute("""
        INSERT INTO catholic_hierarchy (church_id, name, cath_type, cath_detail, city, country, lat, lon)
        VALUES (?, ?, 'holy_see', 'Holy See', ?, ?, ?, ?)
    """, (hs[0], 'Holy See — Vatican City', hs[2], hs[3], hs[4], hs[5]))
else:
    db.execute("""
        INSERT INTO catholic_hierarchy (name, cath_type, cath_detail, country)
        VALUES ('Holy See — Vatican City', 'holy_see', 'Holy See', 'VA')
    """)
holy_see_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
db.commit()
print(f'  Holy See: id={holy_see_id}')

# ═══════════════════════════════════════════════════════════════
# STEP 6: Insert dioceses/archdioceses from territories
# ═══════════════════════════════════════════════════════════════
print('  Inserting dioceses and archdioceses...')

# Map type labels to cath_type
type_map = {'d': 'diocese', 'a': 'archdiocese', 't': 'diocese',  # territorial abbey
            'p': 'diocese',  # territorial prelature
            'e': 'diocese',  # eparchy
            'ar': 'archdiocese',  # archeparchy
            'o': 'other', 'm': 'diocese', 'l': 'diocese'}

# Build a reverse name-mapping for dioceses (normalized for matching)
# Also track territory IDs
territory_id_map = {}  # lower_name -> territory_id

diocese_rows = []
province_rows = {}

for name, t in territories.items():
    t_type = type_map.get(t['type'], 'diocese')
    if t['type'] in ('a', 'ar'):
        t_type = 'archdiocese'
    
    country = t['country']
    metro = t['metro_key']
    rite = t['rite_label']
    
    # Determine province name from metro_key
    province_name = None
    if metro and metro in territories:
        province_name = territories[metro]['full_name']
    
    diocese_rows.append((
        t['full_name'], t_type, t['name'], province_name, country, rite, t['id']
    ))
    territory_id_map[name] = t['id']

# Insert all at once
db.executemany("""
    INSERT INTO catholic_hierarchy 
        (name, cath_type, cath_detail, province, country, rite, territory_id)
    VALUES (?, ?, ?, ?, ?, ?, ?)
""", diocese_rows)
db.commit()
print(f'  {len(diocese_rows)} dioceses/archdioceses inserted')

# Get all inserted IDs keyed by territory_id for linking
territory_hierarchy = {}
cur = db.execute("SELECT id, territory_id, cath_type FROM catholic_hierarchy WHERE territory_id IS NOT NULL")
for r in cur.fetchall():
    territory_hierarchy[r[1]] = {'id': r[0], 'type': r[2]}

# ═══════════════════════════════════════════════════════════════
# STEP 7: Link suffragan dioceses to their archdioceses/provinces
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 7: Linking dioceses to archdioceses/provinces ===')

# For each diocese, find its metropolitan (archdiocese) via metro_key
link_count = 0
for name, t in territories.items():
    t_id = territory_id_map.get(name)
    if not t_id:
        continue
    h_id = territory_hierarchy.get(t_id, {}).get('id')
    if not h_id:
        continue
    
    metro = t['metro_key']
    if metro and metro in territories:
        metro_name = metro
        metro_t_id = territory_id_map.get(metro_name)
        metro_h = territory_hierarchy.get(metro_t_id, {}) if metro_t_id else {}
        metro_id = metro_h.get('id')
        
        if metro_id and t['type'] in ('d', 'e', 'p', 't', 'm', 'l'):
            # This is a suffragan diocese -> link to archdiocese
            db.execute("""
                UPDATE catholic_hierarchy 
                SET parent_id = ?, parent_cath_type = 'archdiocese',
                    relationship = 'suffragan_of',
                    archdiocese = (SELECT name FROM catholic_hierarchy WHERE id = ?)
                WHERE id = ?
            """, (metro_id, metro_id, h_id))
            link_count += 1

db.commit()
print(f'  {link_count} suffragan links created')

# ═══════════════════════════════════════════════════════════════
# STEP 8: Insert provinces and link archdioceses to them
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 8: Creating province entries ===')

# Create province entries for each metropolitan
province_ids = {}
for name, t in territories.items():
    if t['type'] in ('a', 'ar'):  # archdiocese = metropolitan
        metro_t_id = territory_id_map.get(name)
        metro_h = territory_hierarchy.get(metro_t_id, {}) if metro_t_id else {}
        metro_id = metro_h.get('id')
        
        if metro_id and t['metro_key']:
            # The archdiocese's own metro_key IS the province key
            province_name = f"Province of {t['name']}"
            
            db.execute("""
                INSERT INTO catholic_hierarchy 
                    (name, cath_type, cath_detail, country, parent_id, parent_cath_type, relationship)
                VALUES (?, 'province', ?, ?, ?, 'holy_see', 'part_of_conference')
            """, (province_name, f"Metropolitan province of {t['full_name']}", t['country'], holy_see_id))
            
            prov_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            province_ids[name] = prov_id
            
            # Link the archdiocese to this province
            db.execute("""
                UPDATE catholic_hierarchy
                SET parent_id = ?, parent_cath_type = 'province',
                    relationship = 'belongs_to_province',
                    province = ?
                WHERE id = ?
            """, (prov_id, province_name, metro_id))

db.commit()
print(f'  {len(province_ids)} provinces created and linked')

# ═══════════════════════════════════════════════════════════════
# STEP 9: Link parishes (churches) to their dioceses
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 9: Linking parishes to dioceses ===')

# Load church_enrichment diocese data
parish_links = {}  # church_id -> diocese name
cur = db.execute("""
    SELECT church_id, diocese FROM church_enrichment
    WHERE diocese IS NOT NULL AND diocese != ''
""")
for r in cur.fetchall():
    parish_links[r[0]] = r[1]
print(f'  {len(parish_links):,} parish->diocese links from church_enrichment')

# Insert parish entries for Catholic churches that have diocese links
parish_inserts = []
linked_parishes = 0
for church_id, diocese_name in parish_links.items():
    if church_id not in catholic_ids:
        continue
    
    # Find matching territory
    dio_lower = diocese_name.lower().strip()
    dio_h = None
    # Try exact match
    if dio_lower in territory_hierarchy:
        t_id = territory_id_map.get(dio_lower)
        dio_h = territory_hierarchy.get(t_id) if t_id else None
    
    # Try by territory name
    if not dio_h:
        for tname, t in territories.items():
            if tname.startswith(dio_lower) or dio_lower.startswith(tname):
                t_id = territory_id_map.get(tname)
                dio_h = territory_hierarchy.get(t_id) if t_id else None
                break
    
    # Get church data
    church = db.execute("""
        SELECT name, city, state, country, latitude, longitude 
        FROM churches WHERE id = ?
    """, (church_id,)).fetchone()
    if not church:
        continue
    
    parent_id = dio_h['id'] if dio_h else None
    parent_type = dio_h['type'] if dio_h else None
    
    parish_inserts.append((
        church_id, church[0], 'parish', diocese_name, 
        church[1], church[2], church[3], church[4], church[5],
        parent_id, parent_type
    ))
    
    if len(parish_inserts) >= CHUNK:
        db.executemany("""
            INSERT INTO catholic_hierarchy 
                (church_id, name, cath_type, cath_detail, 
                 city, state, country, lat, lon,
                 parent_id, parent_cath_type, relationship)
            VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, ?, ?, 'belongs_to_diocese')
        """, parish_inserts)
        db.commit()
        linked_parishes += len(parish_inserts)
        print(f'    {linked_parishes} parishes linked')
        parish_inserts = []

if parish_inserts:
    db.executemany("""
        INSERT INTO catholic_hierarchy 
            (church_id, name, cath_type, cath_detail,
             city, state, country, lat, lon,
             parent_id, parent_cath_type, relationship)
        VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, ?, ?, 'belongs_to_diocese')
    """, parish_inserts)
    db.commit()
    linked_parishes += len(parish_inserts)

print(f'  Total parishes linked: {linked_parishes:,}')

# ═══════════════════════════════════════════════════════════════
# STEP 10: Link remaining Catholic churches as parishes (no diocese)
# ═══════════════════════════════════════════════════════════════
print('\n=== STEP 10: Inserting remaining Catholic churches ===')

# Find Catholic churches NOT yet in hierarchy
inserted_churches = set(r[0] for r in db.execute(
    "SELECT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL"
).fetchall() if r[0] is not None)

remaining = catholic_ids - inserted_churches
print(f'  {len(remaining):,} remaining Catholic churches to insert')

remaining_inserts = []
for i, church_id in enumerate(remaining):
    church = db.execute("""
        SELECT name, city, state, country, latitude, longitude, landmark_type
        FROM churches WHERE id = ?
    """, (church_id,)).fetchone()
    if not church:
        continue
    
    # Determine cath_type from landmark_type
    lm = (church[6] or '').lower()
    if lm in ('church', 'cathedral'):
        ctype = 'cathedral' if 'cathedral' in (church[0] or '').lower() else 'parish'
    elif lm == 'chapel':
        ctype = 'parish'
    elif lm == 'shrine':
        ctype = 'shrine'
    elif lm == 'basilica':
        ctype = 'basilica'
    else:
        ctype = 'parish'
    
    remaining_inserts.append((
        church_id, church[0], ctype, church[1], church[2], 
        church[3], church[4], church[5]
    ))
    
    if len(remaining_inserts) >= CHUNK or i == len(remaining) - 1:
        db.executemany("""
            INSERT INTO catholic_hierarchy 
                (church_id, name, cath_type, city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, remaining_inserts)
        db.commit()
        remaining_inserts = []
        if i % 10000 == 0 or i == len(remaining) - 1:
            print(f'    {i+1}/{len(remaining)}')

# ═══════════════════════════════════════════════════════════════
# FINAL VERIFICATION
# ═══════════════════════════════════════════════════════════════
print('\n' + '='*60)
print('FINAL VERIFICATION')
print('='*60)

hier_total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy").fetchone()[0]
print(f'\ncatholic_hierarchy total: {hier_total:,}')

cur = db.execute("SELECT cath_type, COUNT(*) FROM catholic_hierarchy GROUP BY cath_type ORDER BY COUNT(*) DESC")
print('\nType breakdown:')
for r in cur:
    print(f'  {r[1]:>8,} | {r[0]}')

# Hierarchy depth
linked = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f'\nLinked entries: {linked:,}')

# Top-level entries
top = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE parent_id IS NULL").fetchone()[0]
print(f'Top-level (unlinked): {top:,}')

# Church-side FTLD verification
total_churches = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
ftld_full = db.execute("SELECT COUNT(*) FROM churches WHERE faith='christian' AND legacy='Catholic' AND tradition='Catholic Churches'").fetchone()[0]
print(f'\nFTLD: {ftld_full:,} Catholic entries with full faith+legacy+tradition out of {total_churches:,} total churches')

# Log final provenance
now = datetime.now().isoformat()
db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('catholic_hierarchy', '_build_catholic_hierarchy.py', now, now,
      total, hier_total, 
      'faith,legacy,tradition,denomination,catholic_hierarchy', 'completed',
      f'FTLD backfill for {total} Catholic entries. catholic_hierarchy: {hier_total} rows, {linked} linked'))
db.commit()

# Sample hierarchy traversal
print('\n=== Sample hierarchy (US) ===')
cur = db.execute("""
    SELECT h1.name, h1.cath_type, h2.name as parent_name, h2.cath_type as parent_type
    FROM catholic_hierarchy h1
    LEFT JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.country = 'US' AND h1.cath_type IN ('archdiocese', 'diocese', 'province')
    ORDER BY h1.cath_type, h1.name
    LIMIT 15
""")
for r in cur:
    print(f'  {str(r[0])[:50]:50s} ({r[1]:12s}) -> {str(r[2] or "-")[:40]:40s} ({str(r[3] or "-"):12s})')

print('\nDone!')
db.close()

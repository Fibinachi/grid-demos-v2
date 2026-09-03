"""Build Eastern Rite eparchy/archeparchy hierarchy + backfill tradition."""
import sqlite3, re
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')

now = datetime.now().isoformat()
CHUNK = 500

# ── STEP 1: Classify Eastern Rite sui iuris churches ──
print('=== STEP 1: Classifying Eastern Rite entries ===')

# Sui iuris church patterns
sui_iuris = {
    'ukrainian': ('Ukrainian Greek Catholic', 'Ukrainian'),
    'melkite': ('Melkite Greek Catholic', 'Melkite'),
    'maronite': ('Maronite Catholic', 'Maronite'),
    'syro malabar': ('Syro-Malabar Catholic', 'Syro-Malabar'),
    'syro-malabar': ('Syro-Malabar Catholic', 'Syro-Malabar'),
    'syro malankara': ('Syro-Malankara Catholic', 'Syro-Malankara'),
    'syro-malankara': ('Syro-Malankara Catholic', 'Syro-Malankara'),
    'chaldean': ('Chaldean Catholic', 'Chaldean'),
    'syriac catholic': ('Syriac Catholic', 'Syriac'),
    'syrian catholic': ('Syriac Catholic', 'Syriac'),
    'armenian catholic': ('Armenian Catholic', 'Armenian'),
    'coptic catholic': ('Coptic Catholic', 'Coptic'),
    'ethiopian catholic': ('Ethiopian Catholic', 'Ethiopian'),
    'eritrean catholic': ('Eritrean Catholic', 'Eritrean'),
    'byzantine catholic': ('Byzantine Catholic', 'Ruthenian'),
    'ruthenian': ('Ruthenian Catholic', 'Ruthenian'),
    'romanian catholic': ('Romanian Catholic', 'Romanian'),
    'romanian greek': ('Romanian Catholic', 'Romanian'),
    'hungarian greek': ('Hungarian Greek Catholic', 'Hungarian'),
    'slovak greek': ('Slovak Greek Catholic', 'Slovak'),
    'bulgarian greek': ('Bulgarian Greek Catholic', 'Bulgarian'),
    'italo-albanian': ('Italo-Albanian Catholic', 'Italo-Albanian'),
    'albanian greek': ('Albanian Greek Catholic', 'Albanian'),
    'russian greek': ('Russian Greek Catholic', 'Russian'),
    'belarusian greek': ('Belarusian Greek Catholic', 'Belarusian'),
    'macedonian greek': ('Macedonian Greek Catholic', 'Macedonian'),
    'georgian byzantine': ('Georgian Byzantine Catholic', 'Georgian'),
    'greek catholic': ('Greek Catholic', 'Greek'),
    'malabar catholic': ('Syro-Malabar Catholic', 'Syro-Malabar'),
    'malankara catholic': ('Syro-Malankara Catholic', 'Syro-Malankara'),
}

# Find and classify
classified = {}  # church_id -> (tradition_name, short_name)
for pattern, (tradition, short) in sui_iuris.items():
    for r in db.execute("""
        SELECT id, name FROM churches 
        WHERE legacy='Catholic' AND name LIKE ?
    """, (f'%{pattern}%',)):
        classified[r[0]] = (tradition, short, r[1])

# Also search by denomination
for pattern, (tradition, short) in sui_iuris.items():
    for r in db.execute("""
        SELECT id, name FROM churches 
        WHERE legacy='Catholic' AND denomination LIKE ?
    """, (f'%{pattern}%',)):
        if r[0] not in classified:
            classified[r[0]] = (tradition, short, r[1])

print(f'  Classified {len(classified)} Eastern Rite entries')

# Show breakdown
from collections import Counter
trad_counts = Counter(v[0] for v in classified.values())
for t, c in trad_counts.most_common():
    print(f'    {c:>4} | {t}')

# ── STEP 2: Backfill tradition for Eastern Rite entries ──
print('\n=== STEP 2: Backfilling tradition ===')
updated = 0
for cid, (tradition, short, name) in classified.items():
    db.execute("UPDATE churches SET tradition = ? WHERE id = ? AND legacy = 'Catholic'", (tradition, cid))
    updated += 1
    if updated % 500 == 0:
        db.commit()
db.commit()
print(f'  {updated} entries updated with sui iuris tradition')

# ── STEP 3: Find eparchy names from church data ──
print('\n=== STEP 3: Extracting eparchy references ===')

# Look for [EPARCHY] or "Eparchy of X" patterns in names/addresses  
eparchy_refs = {}  # eparchy_name -> set of church_ids
for cid, (tradition, short, name) in classified.items():
    # Check for eparchy in church_enrichment
    dio = db.execute("SELECT diocese FROM church_enrichment WHERE church_id = ?", (cid,)).fetchone()
    if dio and dio[0]:
        ename = dio[0]
        # Check if it's an Eastern Rite eparchy (contains Eparchy, Archeparchy, or sui iuris name)
        lower = ename.lower()
        if any(kw in lower for kw in ['eparchy', 'archeparchy', 'exarchate', 
                                        'ukrainian', 'maronite', 'syro', 'chaldean',
                                        'melkite', 'armenian', 'coptic', 'ruthenian']):
            if ename not in eparchy_refs:
                eparchy_refs[ename] = set()
            eparchy_refs[ename].add(cid)

print(f'  Found {len(eparchy_refs)} distinct eparchy references')
for ename, cids in sorted(eparchy_refs.items(), key=lambda x: -len(x[1]))[:20]:
    print(f'    {len(cids):>4} | {ename[:60]}')

# ── STEP 4: Insert eparchies into catholic_hierarchy ──
print('\n=== STEP 4: Inserting eparchies into hierarchy ===')

# First check which Eastern Rite territories we already have
eastern_territories = {}
for r in db.execute("""
    SELECT et.id, et.name, et.full_name, et.dio_type, et.dio_type_label, et.rite_label
    FROM ecclesiastical_territories et
    WHERE et.rite_label IS NOT NULL AND et.rite_label != 'Latin'
"""):
    eastern_territories[r[1].lower()] = {
        'id': r[0], 'name': r[1], 'full': r[2],
        'type': r[3], 'type_label': r[4], 'rite': r[5]
    }
print(f'  {len(eastern_territories)} Eastern Rite territories in DB')

# Insert eparchies that don't exist yet
eparchy_inserts = {}
for ename, cids in eparchy_refs.items():
    ename_lower = ename.lower().strip()
    
    # Check if already in hierarchy
    existing = db.execute("SELECT id FROM catholic_hierarchy WHERE name = ? AND cath_type IN ('diocese', 'archdiocese')", (ename,)).fetchone()
    if existing:
        eparchy_inserts[ename] = existing[0]
        continue
    
    # Check if it matches an existing territory
    matched = False
    for tname, tinfo in eastern_territories.items():
        if tname in ename_lower or ename_lower in tname:
            # Already inserted as territory
            matched = True
            break
    
    if matched:
        continue
    
    # Determine type
    is_archeparchy = any(kw in ename_lower for kw in ['archeparchy', 'major archbishop', 'patriarch'])
    ctype = 'archdiocese' if is_archeparchy else 'diocese'
    
    # Get rite from majority classification of linked churches
    rite_counts = Counter()
    for cid in cids:
        if cid in classified:
            rite_counts[classified[cid][0]] += 1
    most_common_rite = rite_counts.most_common(1)[0][0] if rite_counts else 'Eastern Catholic'
    
    # Lookup short rite label
    rite_map = {
        'Ukrainian Greek Catholic': 'Ukrainian', 'Melkite Greek Catholic': 'Melkite',
        'Maronite Catholic': 'Maronite', 'Syro-Malabar Catholic': 'Syro-Malabar',
        'Syro-Malankara Catholic': 'Syro-Malankara', 'Chaldean Catholic': 'Chaldean',
        'Syriac Catholic': 'Syriac', 'Armenian Catholic': 'Armenian',
        'Coptic Catholic': 'Coptic', 'Ethiopian Catholic': 'Ethiopian',
        'Eritrean Catholic': 'Eritrean', 'Ruthenian Catholic': 'Ruthenian',
        'Romanian Catholic': 'Romanian', 'Byzantine Catholic': 'Byzantine',
    }
    rite_label = rite_map.get(most_common_rite, 'Eastern')
    
    # Insert
    db.execute("""
        INSERT INTO catholic_hierarchy (name, cath_type, cath_detail, rite, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (ename, ctype, f'Eastern Catholic eparchy ({most_common_rite})', rite_label,
          f'Auto-created from church_enrichment.diocese references'))
    inserted_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    eparchy_inserts[ename] = inserted_id

db.commit()
print(f'  Created {len(eparchy_inserts)} new eparchy entries')
total_eastern = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE rite IS NOT NULL AND rite != '' AND rite != 'Latin'").fetchone()[0]
print(f'  Total Eastern Rite in hierarchy: {total_eastern}')

# ── STEP 5: Link parishes to eparchies ──
print('\n=== STEP 5: Linking parishes to eparchies ===')
parish_links = 0
for ename, parent_id in eparchy_inserts.items():
    cids = eparchy_refs.get(ename, set())
    for cid in cids:
        # Check if already in hierarchy
        existing = db.execute("SELECT id FROM catholic_hierarchy WHERE church_id = ? AND cath_type = 'parish'", (cid,)).fetchone()
        if existing:
            db.execute("""
                UPDATE catholic_hierarchy 
                SET parent_id = ?, parent_cath_type = 'diocese',
                    relationship = 'belongs_to_diocese',
                    rite = (SELECT rite FROM catholic_hierarchy WHERE id = ?)
                WHERE id = ?
            """, (parent_id, parent_id, existing[0]))
            parish_links += 1
        else:
            # Insert new parish entry
            ch = db.execute("SELECT name, city, state, country, latitude, longitude FROM churches WHERE id = ?", (cid,)).fetchone()
            if ch:
                rite_label = db.execute("SELECT rite FROM catholic_hierarchy WHERE id = ?", (parent_id,)).fetchone()
                db.execute("""
                    INSERT INTO catholic_hierarchy 
                        (church_id, name, cath_type, city, state, country, lat, lon,
                         parent_id, parent_cath_type, relationship, rite)
                    VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, 'diocese', 'belongs_to_diocese', ?)
                """, (cid, ch[0], ch[1], ch[2], ch[3], ch[4], ch[5], parent_id, rite_label[0] if rite_label else None))
                parish_links += 1
    
    if parish_links % 500 == 0:
        db.commit()

db.commit()
print(f'  {parish_links} parishes linked to eparchies')

# ── STEP 6: Link existing Eastern Rite territories to parishes where applicable ──
print('\n=== STEP 6: Linking existing territory eparchies ===')

# Match existing catholic_hierarchy Eastern Rite dioceses to parishes
for r in db.execute("""
    SELECT h.id, h.name, et.name as tname
    FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type IN ('diocese', 'archdiocese')
      AND et.rite_label IS NOT NULL AND et.rite_label != 'Latin'
      AND h.id NOT IN (SELECT DISTINCT parent_id FROM catholic_hierarchy WHERE relationship = 'belongs_to_diocese')
"""):
    h_id = r[0]
    h_name = r[1]
    tname = r[2]
    
    # Find parishes that mention this eparchy
    for cid, in db.execute("""
        SELECT church_id FROM church_enrichment 
        WHERE diocese LIKE ? AND church_id IN (SELECT id FROM churches WHERE legacy = 'Catholic')
    """, (f'%{tname}%',)):
        # Link parish
        existing = db.execute("SELECT id FROM catholic_hierarchy WHERE church_id = ? AND cath_type = 'parish'", (cid,)).fetchone()
        if existing:
            db.execute("""
                UPDATE catholic_hierarchy SET parent_id = ?, parent_cath_type = 'diocese',
                    relationship = 'belongs_to_diocese'
                WHERE id = ?
            """, (h_id, existing[0]))
        else:
            ch = db.execute("SELECT name, city, state, country, latitude, longitude FROM churches WHERE id = ?", (cid,)).fetchone()
            if ch:
                db.execute("""
                    INSERT INTO catholic_hierarchy 
                        (church_id, name, cath_type, city, state, country, lat, lon,
                         parent_id, parent_cath_type, relationship)
                    VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, 'diocese', 'belongs_to_diocese')
                """, (cid, ch[0], ch[1], ch[2], ch[3], ch[4], ch[5], h_id))

db.commit()

# ── FINAL VERIFICATION ──
print('\n' + '='*60)
print('VERIFICATION')
print('='*60)

erin = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE rite IS NOT NULL AND rite != '' AND rite != 'Latin'").fetchone()[0]
print(f'Eastern Rite in hierarchy: {erin}')

for r in db.execute("""
    SELECT rite, COUNT(*) FROM catholic_hierarchy 
    WHERE rite IS NOT NULL AND rite != '' AND rite != 'Latin' 
    GROUP BY rite ORDER BY COUNT(*) DESC
"""):
    print(f'  {r[1]:>4} | {r[0]}')

# Show sample hierarchy
print('\nSample Eastern Rite hierarchy:')
for r in db.execute("""
    SELECT h1.name, h1.cath_type, h1.rite, h2.name as parent
    FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.rite IS NOT NULL AND h1.rite != '' AND h1.rite != 'Latin'
    LIMIT 15
"""):
    print(f'  {str(r[0])[:40]:40s} ({str(r[1]):12s}) [{str(r[2]):15s}] -> {str(r[3] or "-")[:40]}')

# FTLD verification
ftld = db.execute("SELECT COUNT(*) FROM churches WHERE legacy = 'Catholic' AND tradition != 'Catholic Churches' AND tradition != 'Catholic'").fetchone()[0]
print(f'\nChurches with sui iuris tradition: {ftld}')

# Log provenance
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
    ('eastern_rite_hierarchy', '_build_eastern_hierarchy.py', now, now,
     updated, erin, 'tradition,catholic_hierarchy', 'completed',
     f'Classified {len(classified)} Eastern Rite entries, {erin} in hierarchy'))
db.commit()

print('\nDone!')
db.close()

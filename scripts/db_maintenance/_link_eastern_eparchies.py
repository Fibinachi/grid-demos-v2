"""Link Eastern Rite parishes to eparchies in catholic_hierarchy."""
import sqlite3
from datetime import datetime
from collections import Counter

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

now = datetime.now().isoformat()

# STEP 1: Find all Eastern Rite church IDs and their traditions
print('Finding Eastern Rite entries...')
eastern_ids = set()
trad_map = {}  # church_id -> tradition
for r in db.execute("SELECT id, tradition FROM churches WHERE legacy='Catholic' AND tradition IN ('Ukrainian Greek Catholic','Syro-Malabar Catholic','Maronite Catholic','Syro-Malankara Catholic','Byzantine Catholic','Melkite Greek Catholic','Ruthenian Catholic','Chaldean Catholic','Syriac Catholic','Greek Catholic','Eastern Catholic','Coptic Catholic','Armenian Catholic','Romanian Catholic','Hungarian Greek Catholic','Eritrean Catholic','Ethiopian Catholic')"):
    eastern_ids.add(r[0])
    trad_map[r[0]] = r[1]
print(f'  {len(eastern_ids)} Eastern Rite entries')

# STEP 2: Find eparchy references from church_enrichment
print('\nFinding eparchy references...')
eparchy_refs = {}  # eparchy_name -> list of church_ids
for cid in eastern_ids:
    dio = db.execute("SELECT diocese FROM church_enrichment WHERE church_id = ?", (cid,)).fetchone()
    if dio and dio[0]:
        ename = dio[0].strip()
        lower = ename.lower()
        if any(kw in lower for kw in ['eparchy', 'archeparchy', 'exarchate',
                                        'ukrainian', 'maronite', 'syro', 'chaldean',
                                        'melkite', 'armenian', 'coptic', 'ruthenian',
                                        'byzantine', 'melkite', 'chaldean']):
            if ename not in eparchy_refs:
                eparchy_refs[ename] = []
            eparchy_refs[ename].append(cid)

print(f'  {len(eparchy_refs)} distinct eparchy names found')

# STEP 3: Create eparchy entries in catholic_hierarchy
print('\nCreating eparchy entries...')
created = 0
for ename, cids in sorted(eparchy_refs.items(), key=lambda x: -len(x[1])):
    # Check if already exists
    existing = db.execute("SELECT id FROM catholic_hierarchy WHERE name = ? AND cath_type IN ('diocese','archdiocese')", (ename,)).fetchone()
    if existing:
        continue
    
    # Determine rite from majority of linked churches
    rite_counts = Counter()
    for cid in cids:
        t = trad_map.get(cid, 'Eastern Catholic')
        rite_counts[t] += 1
    
    top_rite = rite_counts.most_common(1)[0][0] if rite_counts else 'Eastern Catholic'
    
    # Determine if archeparchy
    lower = ename.lower()
    if 'archeparchy' in lower or 'major archbishop' in lower:
        ctype = 'archdiocese'
    else:
        ctype = 'diocese'
    
    db.execute("""
        INSERT INTO catholic_hierarchy (name, cath_type, cath_detail, rite, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (ename, ctype, f'{top_rite} eparchy', top_rite.split()[0],
          f'From church_enrichment.diocese ({len(cids)} parishes)'))
    created += 1
    
    if created % 50 == 0:
        db.commit()

db.commit()
print(f'  Created {created} new eparchy entries')

# STEP 4: Link parishes to eparchies
print('\nLinking parishes to eparchies...')
parish_links = 0
for ename, cids in eparchy_refs.items():
    eparchy = db.execute("SELECT id, rite FROM catholic_hierarchy WHERE name = ?", (ename,)).fetchone()
    if not eparchy:
        continue
    eid, erite = eparchy
    
    for cid in cids:
        existing = db.execute("SELECT id FROM catholic_hierarchy WHERE church_id = ? AND cath_type = 'parish'", (cid,)).fetchone()
        
        if existing:
            db.execute("""
                UPDATE catholic_hierarchy SET parent_id = ?, parent_cath_type = 'diocese',
                    relationship = 'belongs_to_diocese', rite = ?
                WHERE id = ?
            """, (eid, erite, existing[0]))
        else:
            ch = db.execute("SELECT name, city, state, country, latitude, longitude FROM churches WHERE id = ?", (cid,)).fetchone()
            if ch:
                db.execute("""
                    INSERT INTO catholic_hierarchy (church_id, name, cath_type, city, state, country, lat, lon,
                        parent_id, parent_cath_type, relationship, rite)
                    VALUES (?, ?, 'parish', ?, ?, ?, ?, ?, ?, 'diocese', 'belongs_to_diocese', ?)
                """, (cid, ch[0], ch[1], ch[2], ch[3], ch[4], ch[5], eid, erite))
        
        parish_links += 1
    
    if parish_links % 500 == 0:
        db.commit()

db.commit()
print(f'  {parish_links} parishes linked to eparchies')

# STEP 5: Link existing Eastern Rite territory entries to parishes
print('\nLinking territory-based eparchies...')
for r in db.execute("""
    SELECT h.id, et.name FROM catholic_hierarchy h
    JOIN ecclesiastical_territories et ON h.territory_id = et.id
    WHERE h.cath_type IN ('diocese','archdiocese')
      AND et.rite_label IS NOT NULL AND et.rite_label != 'Latin'
"""):
    h_id, tname = r
    linked = 0
    for cid in eastern_ids:
        dio = db.execute("SELECT diocese FROM church_enrichment WHERE church_id = ?", (cid,)).fetchone()
        if dio and dio[0] and tname.lower() in dio[0].lower():
            existing = db.execute("SELECT id FROM catholic_hierarchy WHERE church_id = ? AND cath_type = 'parish'", (cid,)).fetchone()
            if existing:
                db.execute("UPDATE catholic_hierarchy SET parent_id = ?, parent_cath_type = 'diocese', relationship = 'belongs_to_diocese' WHERE id = ?", (h_id, existing[0]))
                linked += 1
    
    if linked:
        db.commit()
        print(f'  {tname}: {linked} parishes linked')

# Final count
erin = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE rite IS NOT NULL AND rite != '' AND rite != 'Latin'").fetchone()[0]
linked_parishes = db.execute("""
    SELECT COUNT(*) FROM catholic_hierarchy h1
    JOIN catholic_hierarchy h2 ON h1.parent_id = h2.id
    WHERE h1.relationship = 'belongs_to_diocese' AND h1.rite IS NOT NULL AND h1.rite != '' AND h1.rite != 'Latin'
""").fetchone()[0]

print(f'\nFinal: {erin} Eastern Rite entries in hierarchy, {linked_parishes} linked parishes')

# Log provenance
db.execute("""INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    ('eastern_eparchy_links', '_link_eastern_eparchies.py', now, now,
     erin, 'catholic_hierarchy.parent_id,rite', 'completed',
     f'{created} eparchies created, {parish_links} parishes linked'))
db.commit()

print('\nDone!')
db.close()

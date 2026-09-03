"""
Quick pass: link orphaned cathedrals to dioceses by name/city matching.
With manual overrides for remaining obvious cases.
"""
import sqlite3, re

DB_PATH = "churches.db"
CHUNK_SIZE = 100

# Manual overrides: cathedral_hierarchy_id → diocese_hierarchy_id
MANUAL = {
    # Cathedral of Linz → Diocese of Linz
    # "New Cathedral, Linz" - city extraction fails due to comma
}
# Also add name-based overrides: partial cathedal name substring → diocese name substring
NAME_OVERRIDES = {
    "Linz": "Linz",           # New Cathedral, Linz → Diocese of Linz
    "Bendigo": "Bendigo",     # Sacred Heart Cathedral, Bendigo → ?
    "Palma": "Mallorca",      # Palma Cathedral → Diocese of Mallorca
    "Westminster": "Westminster", # Westminster Cathedral → Archdiocese of Westminster
    "Shrewsbury": "Shrewsbury",   # Shrewsbury Cathedral → Diocese of Shrewsbury
    "Brechin": "Brechin",     # Brechin Cathedral → ?
    "Motherwell": "Motherwell",   # Motherwell Cathedral → Diocese of Motherwell
    "Glasgow": "Glasgow",     # Glasgow Cathedral → Archdiocese of Glasgow
    "Dunkeld": "Dunkeld",     # Dunkeld Cathedral → ?
    "Dunblane": "Dunblane",   # Dunblane Cathedral → ?
    "Dornoch": "Dornoch",     # Dornoch Cathedral → ?
    "Elgin": "Elgin",         # Elgin Cathedral (ruin) → Diocese of Moray
    "Fortrose": "Fortrose",   # Fortrose Cathedral → Diocese of Ross
    "Snizort": "Isle",        # Snizort Cathedral → Diocese of Argyll and The Isles
    "St Andrews": "Saint Andrews", # St Andrews Cathedral → Archdiocese of Saint Andrews and Edinburgh
    "Basse-Terre": "Basse-Terre", # Basse-Terre → Diocese of Basse-Terre
    "Cayenne": "Cayenne",     # Cayenne → Diocese of Cayenne
    "Taiohae": "Taiohae",     # Tai o Hae → Diocese of Taiohae
    "Infanta": "Infanta",     # St. Anthony of Padua Cathedral → Territorial Prelature of Infanta (PH)
    "Basco": "Basco",         # Basco Cathedral → ?
    "Tandag": "Tandag",       # Tandag Cathedral → Diocese of Tandag
    "Surigao": "Surigao",     # Surigao Cathedral → Diocese of Surigao
    "Romblon": "Romblon",     # Romblon Cathedral → Diocese of Romblon
    "Maasin": "Maasin",       # Maasin Cathedral → Diocese of Maasin
    "Malolos": "Malolos",     # Malolos Cathedral → Diocese of Malolos
    "Calapan": "Calapan",     # Calapan Cathedral → Apostolic Vicariate of Calapan
    "Jolo": "Jolo",           # Jolo Cathedral → Apostolic Vicariate of Jolo
    "Dumaguete": "Dumaguete", # Dumaguete Cathedral → Diocese of Dumaguete
    "Tagbilaran": "Tagbilaran", # Tagbilaran Cathedral → Diocese of Tagbilaran
    "Gamu": "Ilagan",         # Gamu Cathedral → Diocese of Ilagan
    "Isabela City": "Isabela", # Isabela Cathedral → Prelature of Isabela
    "Zamboanga": "Zamboanga", # Zamboanga Cathedral → Archdiocese of Zamboanga
    "Puerto Princesa": "Puerto Princesa", # → Apostolic Vicariate of Puerto Princesa  
    "San Jose": "San Jose",   # San Jose de Antique → Diocese of San Jose de Antique
    "Marawi": "Marawi",       # Marawi Cathedral → Prelature of Marawi
}

def extract_city_candidates(name, city_field):
    candidates = []
    if city_field and city_field.strip():
        candidates.append(city_field.strip())
    if not name:
        return candidates
    cleaned = name
    cleaned = re.sub(r'\bCathedral\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\b(Co-|Co )?Cathedral\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bBasilica\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\bMetropolitan\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'\([^)]*\)', '', cleaned)
    cleaned = re.sub(r'\b(Church|of|the|Our|Lady|Saint|St\.|San|Santo|Santa|São|Don|Notre|Dame|Du|Dom|Mariä|Himmelfahrt)\b', '', cleaned, flags=re.I)
    cleaned = re.sub(r'[;,].*$', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    for w in cleaned.split():
        if len(w) > 2 and w[0].isupper():
            candidates.append(w)
    m = re.match(r'^([A-Za-zÀ-ÖØ-öø-ÿ -]+)\s+Cathedral', name)
    if m:
        candidates.append(m.group(1).strip())
    m = re.search(r'Cathedral\s+of\s+([A-Za-zÀ-ÖØ-öø-ÿ -]+)', name)
    if m:
        candidates.append(m.group(1).strip())
    return list(set(candidates))

def find_diocese(c, city_candidate, country):
    if not city_candidate:
        return None
    cc = city_candidate.strip().lower()
    
    # Check name overrides first
    for key, val in NAME_OVERRIDES.items():
        if key.lower() in cc or cc in key.lower():
            c.execute("""
                SELECT id, name FROM catholic_hierarchy
                WHERE cath_type IN ('diocese','archdiocese','eparchy','archeparchy',
                                    'territorial_prelature','apostolic_vicariate','prelature')
                AND LOWER(country) = LOWER(?) AND LOWER(name) LIKE ?
                LIMIT 1
            """, (country, f'%{val.lower()}%'))
            row = c.fetchone()
            if row:
                return row
    
    c.execute("""
        SELECT id, name FROM catholic_hierarchy
        WHERE cath_type IN ('diocese','archdiocese','eparchy','archeparchy',
                            'territorial_prelature','apostolic_vicariate','prelature')
        AND LOWER(country) = LOWER(?) AND LOWER(name) LIKE ?
        LIMIT 1
    """, (country, f'%{cc}%'))
    row = c.fetchone()
    if row:
        return row
    
    # Try diacritics
    cc_simple = cc.replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')
    cc_simple = cc_simple.replace('à','a').replace('è','e').replace('ì','i').replace('ò','o').replace('ù','u')
    cc_simple = cc_simple.replace('ä','a').replace('ë','e').replace('ï','i').replace('ö','o').replace('ü','u')
    cc_simple = cc_simple.replace('ñ','n').replace('ç','c')
    if cc_simple != cc:
        c.execute("""
            SELECT id, name FROM catholic_hierarchy
            WHERE cath_type IN ('diocese','archdiocese','eparchy','archeparchy',
                                'territorial_prelature','apostolic_vicariate','prelature')
            AND LOWER(country) = LOWER(?) AND LOWER(name) LIKE ?
            LIMIT 1
        """, (country, f'%{cc_simple}%'))
        row = c.fetchone()
        if row:
            return row
    return None

db = sqlite3.connect(DB_PATH)
c = db.cursor()

c.execute("""
    SELECT ch.id, ch.name, ch.city, ch.state, ch.country
    FROM catholic_hierarchy ch
    WHERE ch.cath_type = 'cathedral' AND ch.parent_id IS NULL
    ORDER BY ch.country, ch.city
""")
orphans = c.fetchall()
print(f"Orphaned cathedrals: {len(orphans)}")

matched = []
unmatched = []
for hid, name, city, state, country in orphans:
    if not country:
        unmatched.append((hid, name, "no country"))
        continue
    candidates = extract_city_candidates(name or "", city)
    found = None
    for cand in candidates:
        found = find_diocese(c, cand, country)
        if found:
            break
    if found:
        matched.append((hid, found[0], found[1], name, city, country))
    else:
        unmatched.append((hid, name, str(candidates[:3])))

print(f"Matched: {len(matched)}")
print(f"Unmatched: {len(unmatched)}")

print(f"\n=== Unmatched ({len(unmatched)}) ===")
for hid, name, reason in unmatched:
    print(f"  #{hid}: '{name[:50]}' | candidates={reason}")

# Execute
print(f"\nUpdating {len(matched)} entries...")
updated = 0
for hid, did, dname, cname, city, country in matched:
    c.execute("""
        UPDATE catholic_hierarchy
        SET parent_id = ?, parent_cath_type = 'diocese',
            relationship = 'seat_of',
            notes = COALESCE(notes, '') || ' | Linked by name match'
        WHERE id = ?
    """, (did, hid))
    updated += 1
    if updated % CHUNK_SIZE == 0:
        db.commit()
        print(f"  {updated}/{len(matched)}...")

db.commit()
print(f"Updated: {updated}")

c.execute("SELECT COUNT(DISTINCT parent_id) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NOT NULL")
covered = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NULL")
remaining = c.fetchone()[0]
print(f"\nDioceses with cathedral: {covered}")
print(f"Still orphaned: {remaining}")

# Log provenance
import datetime
ts = datetime.datetime.now().isoformat()
c.execute("""
    INSERT INTO provenance_log
        (source, script_name, started_at, completed_at,
         churches_updated, churches_inserted, fields_populated,
         records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("link_cathedral_seats_name", "_quick_cathedral_match.py",
      ts, ts,
      updated, 0, "parent_id,parent_cath_type,relationship",
      len(orphans), len(matched),
      f"Name-based matching pass. {remaining} remain orphaned (historical ruins, mis-geocoded, no matching diocese)."))
db.commit()
db.close()
print("✅ Done!")

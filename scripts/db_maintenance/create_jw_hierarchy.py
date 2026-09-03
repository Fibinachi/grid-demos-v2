"""
Create the jw_hierarchy table and populate it from churches data.
JW organizational structure modeling for Jehovah's Witnesses.

Usage:
    python scripts/db_maintenance/create_jw_hierarchy.py
"""
import sqlite3
import re
from datetime import datetime

CHUNK = 500


def detect_jw_type(name, country):
    """Detect the JW organization type from a normalized name."""
    low = name.lower().strip()
    
    # Early rejection: Spanish/Portuguese evangelical churches are NOT JW
    non_jw_patterns = [
        'iglesia', 'igreja', 'santidad a jehova', 'avivamiento',
        'jesucristo', 'cristo', 'alianza', 'mision profetica',
        'centro cristiano', 'centro evangelistico',
        'ministerio de dios', 'ministerio cristiano',
        'rock of ages', 'bear witness',
        'jehova roca', 'jehova pastor', 'jehova es mi',
        'jehova salvacion', 'jehova guerrero',
        'jehova proveera', 'jehova shama',
        'puerta de',
    ]
    for pat in non_jw_patterns:
        if pat in low:
            return 'other', None
    
    # Assembly Hall / Assemblyen / Assembly Hallen
    if low.startswith('assembly hall of jehovah') or 'assembly hall' in low:
        return 'assembly_hall', None
    if low.startswith('salon de asambleas') or low.startswith('sala de asambleas'):
        return 'assembly_hall', None
    if 'assemblyen' in low or 'assemblies of jehovah' in low:
        return 'assembly_hall', None
    
    # Bethel / Branch Office
    if 'bethel' in low:
        return 'bethel', None
    if low.startswith('branch office'):
        return 'bethel', None
    
    # Circuit — extract circuit code
    circuit_match = re.search(
        r'(\w+(?:\s+\w+)*)\s+circuit\s+([\d]+[a-z]?(?:-[\d]+[a-z]?)?)\s+of\s+jehovah',
        low, re.IGNORECASE
    )
    if circuit_match:
        circuit_code = f"{circuit_match.group(1)}-{circuit_match.group(2)}".upper()
        return 'circuit', circuit_code
    
    # Short standalone circuit patterns
    if low.startswith('circuit') and ('jehov' in low or 'witness' in low):
        return 'circuit', None
    if 'circuit overseer' in low:
        return 'circuit', None
    
    # Kingdom Hall (normalized forms)
    if low.startswith('kingdom hall of jehovah'):
        return 'kingdom_hall', None
    if low.startswith('salao do reino') or low.startswith('salon del reino') or \
       low.startswith('salón del reino') or low.startswith('sála kráľovstva') or \
       low.startswith('sala krolestwa') or low.startswith('sala królestwa') or \
       low.startswith('dvorana jehovinih') or low.startswith('königreichssaal') or \
       low.startswith('salle du royaume') or low.startswith('sala do regno'):
        return 'kingdom_hall', None
    
    # Short standalone Kingdom Hall
    if low in ('kingdom hall of jehovah\'s witnesses', 'kingdom hall', 'jw kingdom hall',
               'kingdom hall of jehova', 'kingdom hall jehova',
               'kingdom hall of jehovah witnesses', 'kingdom hl'):
        return 'kingdom_hall', None
    
    # "Kingdom" + "Witnesses" / "Jehov" variants
    if 'kingdom' in low and ('jehov' in low or 'witness' in low):
        return 'kingdom_hall', None
    
    # Convention
    if low.startswith('convention') and ('jehov' in low or 'witness' in low):
        return 'convention', None
    if 'convention' in low and 'jehov' in low:
        return 'convention', None
    if 'convention' in low and 'witness' in low:
        return 'convention', None
    
    # Study
    if 'study' in low or 'bible study' in low:
        if 'jehov' in low or 'witness' in low:
            return 'study', None
    
    # Congregation (normalized or original)
    if 'congregation' in low:
        return 'congregation', None
    
    # "Jehovah's Witnesses" standalone (all languages)
    if low.rstrip('.') in (
        "jehovah's witnesses", "jehovah witnesses", "jehovah witness",
        "jehovah's witness", "jehovahs witnesses",
        "witnesses of jehovah", "witness of jehovah",
        "testigos de jehová", "testigos de jehova",
        "testemunhas de jeová", "testemunhas de jeova",
        "jehovas vitnen", "jehovan todistajat",
        "jehovas świadkowie", "jehovas swiadkowie",
        "svědkové jehovovi", "jehovini svjedoci",
        "jehovas liecinieki", "jehoova tunnistajad",
        "jehova tanúi", "jehovovi svedoci",
        "martorii lui iehova",
    ):
        return 'congregation', None
    
    # "Jehovah's Church" — likely a Kingdom Hall
    if low.startswith('jehovah') and low.endswith('church'):
        return 'kingdom_hall', None
    
    # "Testigos de Jehová" variants
    if low.startswith('testigos de jehová') or low.startswith('testigos de jehova'):
        return 'congregation', None
    if low.startswith('testemunhas de jeová') or low.startswith('testemunhas de jeova'):
        return 'congregation', None
    if low.startswith('iglesia') and ('jehová' in low or 'jehova' in low) and 'testigos' not in low:
        return 'kingdom_hall', None
    
    # "Jehovah's Zeugen" (German)
    if low.startswith("jehovah's zeugen") or low.startswith('jehovas zeugen'):
        return 'congregation', None
    
    # Generic JW — anything with Jehovah/Witnesses in it
    if 'jehov' in low or 'witness' in low:
        return 'other', None
    
    # Non-English "Witness" equivalents
    if any(w in low for w in ['svjedok', 'svjedoci', 'svedkov', 'svedkowie',
                               'svědkové', 'vitnen', 'todistajat', 'tunnistajad',
                               'liecinieki', 'vitne', 'vitner', 'tanúi',
                               'martorii', 'svedoci']):
        return 'other', None
    
    return 'other', None


def extract_detail(name, jw_type, country):
    """Extract additional detail from name based on type."""
    low = name.lower().strip()
    
    if jw_type == 'circuit':
        # Try to extract language/ethnic detail
        detail = None
        for kw in ['arabic', 'cantonese', 'chinese', 'french', 'greek', 'hindi',
                    'iloko', 'korean', 'portuguese', 'punjabi', 'russian', 'spanish',
                    'swahili', 'tagalog', 'tamil', 'tigrinya', 'sign language']:
            if kw in low:
                detail = kw.title()
                break
        return detail
    
    if jw_type == 'kingdom_hall':
        # Extract city suffix after em-dash
        m = re.search(r'\u2014\s*(.+)$', name)
        if m:
            return m.group(1).strip()
        return None
    
    if jw_type == 'congregation':
        # Extract congregation name: the text before "Congregation of Jehovah's Witnesses"
        # Pattern: "XXX Congregation of Jehovah's Witnesses"
        # Also: "XXX Congregation of Jehovah's Witnesses, CITY, PROVINCE"
        
        # Try to match: "CITY Congregation of Jehovah's Witnesses" or "XXX Congregation ..."
        m = re.search(r'congregation\s+of\s+jehovah', low)
        if m:
            # Get text before "congregation of jehovah" — that's the congregation name
            before = name[:m.start()].strip().rstrip(',').strip()
            if before:
                return before
            # If nothing before, check after for comma-separated city
            after_text = name[m.end():].strip()
            parts = [p.strip() for p in after_text.split(',') if p.strip()]
            if parts:
                return parts[0]
        return None
    
    return None


def main():
    db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    c = db.cursor()
    
    print("=== JW Hierarchy Creator ===")
    
    # Step 1: Create the table if not exists
    print("Creating jw_hierarchy table...")
    c.execute("""
        CREATE TABLE IF NOT EXISTS jw_hierarchy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER REFERENCES jw_hierarchy(id),
            church_id INTEGER,
            name TEXT NOT NULL,
            original_name TEXT,
            jw_type TEXT NOT NULL CHECK(jw_type IN (
                'kingdom_hall', 'assembly_hall', 'circuit',
                'congregation', 'study', 'convention', 'bethel', 'other'
            )),
            jw_detail TEXT,
            circuit_code TEXT,
            city TEXT,
            state TEXT,
            country TEXT,
            lat REAL,
            lon REAL,
            parent_jw_type TEXT,
            relationship TEXT CHECK(relationship IN (
                'meets_at',
                'belongs_to_circuit',
                'served_by',
                'affiliated_with'
            )),
            ministries TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            CONSTRAINT unique_link UNIQUE(church_id, parent_id, relationship)
        )
    """)
    db.commit()
    
    # Step 2: Check if already populated
    existing = c.execute("SELECT COUNT(*) FROM jw_hierarchy").fetchone()[0]
    if existing > 0:
        print(f"  jw_hierarchy already has {existing:,} rows — deleting and rebuilding...")
        c.execute("DELETE FROM jw_hierarchy")
        db.commit()
    
    print("Gathering JW entries...")
    
    # Build the JW name matching WHERE clause (expanded patterns)
    jw_where = """
        (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%' OR name LIKE '%Jehova%'
           OR name LIKE '%Assembly%Hall%Jehov%' OR name LIKE '%Witnesses%'
           OR name LIKE '%Witness%' OR name LIKE '%Testigos%Jehova%'
           OR name LIKE '%Testemunha%Jeova%' OR name LIKE '%Testigos%Jehov%'
           OR name LIKE '%Salon%Reino%' OR name LIKE '%Salao%Reino%'
           OR name LIKE '%Salón%Reino%' OR name LIKE '%Sala%Reino%'
           OR name LIKE '%Königreichssaal%' OR name LIKE '%Salle%Royaume%'
           OR name LIKE '%Dvorana%Jehovinih%' OR name LIKE '%Sála%kráľovstva%'
           OR name LIKE '%Sala%Królestwa%' OR name LIKE '%Sala%krolestwa%'
           OR name LIKE '%Jehovas%vitnen%' OR name LIKE '%svědkové%')
        AND name NOT LIKE '%Universal%' AND name NOT LIKE '%IURD%'
        AND name NOT LIKE '%JIREH%' AND name NOT LIKE '%Jireh%'
        AND name NOT LIKE '%BAPTIST%' AND name NOT LIKE '%Baptist%'
        AND name NOT LIKE '%LUTHERAN%' AND name NOT LIKE '%Lutheran%'
        AND name NOT LIKE '%SHAMMAH%' AND name NOT LIKE '%RAPHA%'
        AND name NOT LIKE '%MINISTRIES%' AND name NOT LIKE '%Ministries%'
        AND name NOT LIKE '%METHODIST%' AND name NOT LIKE '%Pentecostal%'
        AND name NOT LIKE '%PENTECOSTAL%' AND name NOT LIKE '%CHRISTIAN%'
        AND name NOT LIKE '%FELLOWSHIP%' AND name NOT LIKE '%Fellowship%'
        AND name NOT LIKE '%PRAISE%' AND name NOT LIKE '%Praise%'
        AND name NOT LIKE '%WORSHIP%' AND name NOT LIKE '%Worship%'
        AND name NOT LIKE '%COMMUNITY%' AND name NOT LIKE '%Community%'
        AND name NOT LIKE '%MISSIONARY%' AND name NOT LIKE '%Missionary%'
        AND name NOT LIKE '%DELIVERANCE%' AND name NOT LIKE '%NISSI%'
        AND name NOT LIKE '%Nissi%' AND name NOT LIKE '%SAMA%' AND name NOT LIKE '%Sama%'
        AND name NOT LIKE '%SHALOM%' AND name NOT LIKE '%Shalom%'
        AND name NOT LIKE '%CHURCH OF%' AND name NOT LIKE '%Church of%'
        AND name NOT LIKE '%GOSPEL%' AND name NOT LIKE '%Gospel%'
        AND name NOT LIKE '%ROI%' AND name NOT LIKE '%Rohi%'
        AND name NOT LIKE '%EL BUEN PASTOR%' AND name NOT LIKE '%PRAYER%'
        AND name NOT LIKE '%Prayer%' AND name NOT LIKE '%HOUSE OF%'
        AND name NOT LIKE '%House of%'
        -- Spanish/Portuguese non-JW evangelical churches
        AND name NOT LIKE '%IGLESIA%' AND name NOT LIKE '%IGREJA%'
        AND name NOT LIKE '%SANTIDAD%' AND name NOT LIKE '%AVIVAMIENTO%'
        AND name NOT LIKE '%JESUCRISTO%' AND name NOT LIKE '%CRISTO%'
        AND name NOT LIKE '%ALIANZA%' AND name NOT LIKE '%MISION%'
        AND name NOT LIKE '%CENTRO CRISTIANO%' AND name NOT LIKE '%CENTRO EVANGELISTICO%'
        AND name NOT LIKE '%MINISTERIO DE DIOS%' AND name NOT LIKE '%MINISTERIO CRISTIANO%'
        AND name NOT LIKE '%PROFETICA%' AND name NOT LIKE '%PUERTA DE%'
        -- Hebrew divine-name phrases used by non-JW churches
        AND name NOT LIKE '%JEHOVA%ROCA%' AND name NOT LIKE '%JEHOVA%PASTOR%'
        AND name NOT LIKE '%JEHOVA%SALVACION%' AND name NOT LIKE '%JEHOVA%GUERRERO%'
        AND name NOT LIKE '%JEHOVA%PROVEERA%' AND name NOT LIKE '%JEHOVA%SHAMA%'
        AND name NOT LIKE '%JEHOVA%ROPH%' AND name NOT LIKE '%JEHOVA%SHALOM%'
        AND name NOT LIKE '%ROCK OF AGES%' AND name NOT LIKE '%BEAR WITNESS%'
    """
    
    rows = c.execute(f"""
        SELECT id, name, city, state, country, latitude, longitude, source
        FROM churches
        WHERE id IS NOT NULL AND {jw_where}
        ORDER BY name
    """).fetchall()
    
    null_rows = c.execute(f"""
        SELECT id, name, city, state, country, latitude, longitude, source
        FROM churches
        WHERE id IS NULL AND {jw_where}
        ORDER BY name
    """).fetchall()
    
    total = len(rows) + len(null_rows)
    print(f"Found {total:,} JW entries ({len(rows):,} with valid id, {len(null_rows):,} with NULL id)")
    
    # Step 3: Classify and insert into hierarchy
    all_rows = list(rows) + list(null_rows)
    print("Classifying and inserting...")
    c.execute("BEGIN TRANSACTION")
    
    type_counts = {}
    inserted = 0
    
    for church_id, name, city, state, country, lat, lon, source in all_rows:
        jw_type, circuit_code = detect_jw_type(name, country or '')
        detail = extract_detail(name, jw_type, country or '')
        
        type_counts[jw_type] = type_counts.get(jw_type, 0) + 1
        
        city = city if city and city != 'None' else None
        state = state if state and state != 'None' else None
        country = country if country and country != 'None' else None
        
        c.execute("""
            INSERT INTO jw_hierarchy
                (church_id, name, jw_type, jw_detail, circuit_code,
                 city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (church_id, name, jw_type, detail, circuit_code,
              city, state, country, lat, lon))
        
        inserted += 1
        if inserted % CHUNK == 0:
            c.execute("COMMIT"); c.execute("BEGIN TRANSACTION")
            print(f"  Inserted {inserted:,}/{total:,}...", flush=True)
    
    c.execute("COMMIT")
    
    print(f"\n✓ {inserted:,} rows inserted into jw_hierarchy")
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:20s}: {cnt:>6,}")
    
    # Step 4: Create indexes
    print("\nCreating indexes...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jw_hierarchy_type ON jw_hierarchy(jw_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jw_hierarchy_circuit ON jw_hierarchy(circuit_code)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jw_hierarchy_parent ON jw_hierarchy(parent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jw_hierarchy_church ON jw_hierarchy(church_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jw_hierarchy_city_country ON jw_hierarchy(city, country)")
    db.commit()
    
    # Log provenance
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                     churches_updated, fields_populated, records_attempted, status)
        VALUES ('jw_hierarchy', 'create_jw_hierarchy.py', ?, ?, ?, ?, ?, 'completed')
    """, (now, datetime.now().isoformat(), inserted, 'jw_type,jw_detail,circuit_code', total))
    db.commit()
    
    print("  Done!")
    
    db.close()


if __name__ == '__main__':
    main()

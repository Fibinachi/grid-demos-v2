"""
Salvation Army Name Normalizer + Hierarchy Builder

Classifies all Salvation Army entries by type (corps, citadel, temple, hall,
hq, social_service, etc.), normalizes names, and builds a hierarchy table
(sa_hierarchy) linking entries where possible.

Usage:
    python scripts/db_maintenance/standardize_salvation_army.py          # run for real
    python scripts/db_maintenance/standardize_salvation_army.py --dry-run  # preview only
"""
import sqlite3, re, sys, os
from datetime import datetime

CHUNK = 500

# ── The Salvation Army type detection patterns ──
# Order matters: more specific patterns first

TYPE_PATTERNS = [
    # (pattern_flag, type_code, description_prefix)
    ('governing_council',   'governing_council', 'Governing Council'),
    ('thrift',              'social_service',    'Thrift Store'),
    ('arc',                 'social_service',    'Adult Rehabilitation Centre'),
    ('red shield',          'social_service',    'Red Shield'),
    ('social',              'social_service',    'Social Services'),
    ('employment',          'social_service',    'Employment Services'),
    ('songster',            'musical_group',     'Songsters'),
    ('band',                'musical_group',     'Band'),
    ('corps',               'corps',             'Corps'),
    ('citadel',             'citadel',           'Citadel'),
    ('temple',              'temple',            'Temple'),
    ('chapel',              'chapel',            'Chapel'),
    ('hall',                'hall',              'Hall'),
    ('hq',                  'hq',                'Headquarters'),
    ('headquarters',        'hq',                'Headquarters'),
    ('dhq',                 'hq',                'Divisional HQ'),
    ('thq',                 'hq',                'Territorial HQ'),
    ('territor',            'hq',                'Territorial'),
    ('division',            'hq',                'Divisional'),
    ('divisional',          'hq',                'Divisional HQ'),
    ('school',              'school',            'School'),
    ('community church',    'community_church',  'Community Church'),
    ('community centre',    'community_church',  'Community Centre'),
    ('community center',    'community_church',  'Community Center'),
    ('community church',    'community_church',  'Community Church'),
    ('worship center',      'church',            'Worship Center'),
    ('worship centre',      'church',            'Worship Centre'),
    ('church',              'church',            'Church'),
]

# Type ordering for hierarchy (0 = top)
TYPE_ORDER = {
    'governing_council': 1,
    'hq': 2,
    'generic': 3,
    'church': 4,
    'corps': 4,
    'citadel': 4,
    'temple': 4,
    'hall': 4,
    'chapel': 4,
    'community_church': 4,
    'school': 5,
    'social_service': 5,
    'musical_group': 5,
    'other': 5,
}


def fix_apost(s):
    """Normalize unicode apostrophes."""
    for ch in '\u2019\u2018\u201a\u201b\u00c6\u00e6':
        s = s.replace(ch, "'")
    s = s.replace('\u00c6', "'").replace('\u00e6', "'")
    s = s.replace('Æ', "'").replace('æ', "'")
    return s


def classify_sa_name(name, city, country):
    """
    Classify a Salvation Army entry by type and extract detail.
    Returns (sa_type, detail, normalized_name, normalized_city).
    """
    orig = name or ''
    low = orig.lower().strip()
    city_low = (city or '').lower().strip()
    
    # Detect foreign language variants
    french = 'armée du salut' in low or 'armee du salut' in low
    german = 'heilsarmee' in low
    swedish = 'frälsningsarmén' in low or 'fralsningsarmen' in low
    norwegian = 'frelsesarmeen' in low
    finnish = 'pelastusarmeija' in low
    spanish = 'ejército de salvación' in low or 'ejercito de salvacion' in low
    portuguese = 'exército de salvação' in low or 'exercito de salvacao' in low
    
    is_foreign = french or german or swedish or norwegian or finnish or spanish or portuguese
    
    # Flags for type detection
    has_hq = bool(re.search(r'\bHQ\b|HEADQUARTERS|DHQ|THQ', orig, re.IGNORECASE))
    has_territor = 'territor' in low
    has_division = bool(re.search(r'\bdivision\b', low)) and not has_hq
    has_divisional = 'divisional' in low
    # Use string containment (not word boundaries) for keywords that may appear
    # mid-word (e.g., "NazCorps", "Songsters", "Band")
    has_corps = 'corps' in low
    has_citadel = 'citadel' in low
    has_temple = 'temple' in low and 'temple corps' not in low
    has_hall = bool(re.search(r'(?<!\w)hall(?!\w)', low)) and 'kingdom' not in low
    has_chapel = 'chapel' in low
    has_church = bool(re.search(r'(?<!\w)church(?!\w)', low))
    has_community = 'community' in low
    has_thrift = 'thrift' in low
    has_arc = 'arc' in [w.strip().strip('(') for w in low.split()] and not has_hq
    has_social = 'social' in low
    has_employment = 'employment' in low
    has_songster = 'songster' in low
    has_band = 'band' in low.split()  # 'band' as a whole word
    has_school = 'school' in low
    has_governing = 'governing council' in low
    has_redshield = 'red shield' in low
    has_worship = 'worship' in low
    has_centre = 'centre' in low or 'center' in low
    
    # ── Extract city from name if available ──
    extracted_city = None
    
    # Try to extract city from patterns like "Salvation Army - City" or "City Salvation Army"
    # Strip "Salvation Army" / "SALVATION ARMY" / foreign variants to see what's left
    if not has_governing:
        # Various patterns to strip
        base = orig
        for prefix in ['THE SALVATION ARMY - ', 'THE SALVATION ARMY ', 'SALVATION ARMY - ', 
                        'SALVATION ARMY ', 'Salvation Army - ', 'Salvation Army ', 'salvation army - ',
                        'salvation army ', 'Salvation army - ', 'Salvation army ']:
            if base.upper().startswith(prefix.upper()):
                base = base[len(prefix):]
                break
        
        # Also try stripping from the end
        for suffix in [' - THE SALVATION ARMY', ' - THE SALVATION ARMY', ' - Salvation Army',
                       ', THE SALVATION ARMY', ', The Salvation Army', ', the Salvation Army',
                       ' THE SALVATION ARMY', ' The Salvation Army']:
            if base.upper().endswith(suffix.upper()):
                base = base[:-len(suffix)]
                break
        
        # Also try stripping "Salvation Army" from anywhere in the string
        base = re.sub(r'\bSalvation Army\b', '', base, flags=re.IGNORECASE).strip()
        base = re.sub(r'\bSALVATION ARMY\b', '', base).strip()
        base = re.sub(r'[,\-:\s]+$', '', base).strip()
        base = re.sub(r'^[,\-:\s]+', '', base).strip()
        
        # If we have a remaining meaningful fragment, it might be a city or corps name
        if base and len(base) > 1 and not base[0].isdigit():
            # Check it doesn't look like a type keyword
            type_words = {'corps', 'citadel', 'temple', 'chapel', 'hall', 'church',
                         'community', 'thrift', 'social', 'arc', 'employment',
                         'songster', 'band', 'school', 'hq', 'headquarters',
                         'dhq', 'thq', 'worship', 'centre', 'center',
                         'ministries', 'outreach', 'family', 'youth', 'senior',
                         'home', 'lodge', 'manor', 'court', 'hostel', 'shelter',
                         'services', 'residences', 'development', 'components',
                         'drop', 'box', 'donation', 'shop', 'charity', 'store',
                         'national', 'england', 'australia', 'corp'}
            base_words = set(w.lower().strip('()"\'') for w in re.split(r'[\s,]+', base) if w.strip('()"\''))
            if not base_words.issubset(type_words):
                extracted_city = base.strip().strip('()"\' ').strip('- ')
    
    # ── Determine SA type ──
    # Check governing council first (may contain French text)
    if has_governing:
        sa_type = 'governing_council'
        detail = 'Canada Governing Council'
        normalized = orig  # Keep as-is, it's a legal name
        return sa_type, detail, normalized, extracted_city

    # ── Foreign language entries should use their native name ──
    if is_foreign and not has_corps and not has_citadel and not has_temple:
        # For foreign languages, use native name without English keyword matching
        if french:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Armée du Salut {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif german:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Heilsarmee {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif swedish:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Frälsningsarmén {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif norwegian:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Frelsesarmeen {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif finnish:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Pelastusarmeija {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif spanish:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Ejército de Salvación {('— ' + extracted_city) if extracted_city else ''}".strip()
        elif portuguese:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = f"Exército de Salvação {('— ' + extracted_city) if extracted_city else ''}".strip()
        else:
            sa_type = 'church'
            detail = extracted_city or city or ''
            normalized = orig
        return sa_type, detail, normalized.strip(), extracted_city

    elif has_thrift:
        sa_type = 'social_service'
        detail = 'Thrift Store'
        normalized = f"The Salvation Army Thrift Store {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_arc and not has_hq:
        sa_type = 'social_service'
        detail = 'ARC'
        normalized = f"The Salvation Army ARC {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_redshield:
        sa_type = 'social_service'
        detail = 'Red Shield'
        normalized = f"The Salvation Army Red Shield {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_social:
        sa_type = 'social_service'
        detail = extracted_city or 'Social Services'
        normalized = f"The Salvation Army Social Services {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_employment:
        sa_type = 'social_service'
        detail = 'Employment Services'
        normalized = f"The Salvation Army Employment Services {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_songster:
        sa_type = 'musical_group'
        detail = extracted_city or 'Songsters'
        normalized = f"The Salvation Army Songsters {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_band:
        sa_type = 'musical_group'
        detail = extracted_city or 'Band'
        normalized = f"The Salvation Army Band {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_hq or has_territor or has_division or has_divisional:
        sa_type = 'hq'
        if has_territor and 'headquarters' in low:
            hq_name = extracted_city or 'Territorial'
            detail = hq_name
            normalized = f"The Salvation Army — {hq_name} Territorial HQ"
        elif has_division and 'division' in low and 'territor' not in low:
            div_name = extracted_city or 'Divisional'
            detail = div_name
            normalized = f"The Salvation Army — {div_name} Division"
        elif has_hq:
            hq_name = extracted_city or city or 'Headquarters'
            detail = hq_name
            normalized = f"The Salvation Army — {hq_name} HQ"
        else:
            hq_name = extracted_city or city or 'Unknown'
            detail = hq_name
            normalized = f"The Salvation Army — {hq_name} HQ"
    elif has_school:
        sa_type = 'school'
        detail = extracted_city or 'School'
        normalized = f"The Salvation Army School {('— ' + extracted_city) if extracted_city else ''}".strip()
    elif has_corps:
        sa_type = 'corps'
        # Extract corps name
        corps_name = extracted_city
        if not corps_name:
            # Try harder - look for "X Corps" pattern
            corps_match = re.search(r'([\w\s\'-]+?)\s+Corps', orig, re.IGNORECASE)
            if corps_match:
                corps_name = corps_match.group(1).strip()
                # Filter out noise
                if corps_name.upper() in ('SALVATION ARMY', 'THE SALVATION ARMY', ''):
                    corps_name = None
        detail = corps_name or city or 'Unknown'
        # Avoid "Corps Corps" if detail already has it
        if detail.upper().endswith('CORPS'):
            normalized = f"The Salvation Army — {detail}"
        else:
            normalized = f"The Salvation Army — {detail} Corps"
    elif has_citadel:
        sa_type = 'citadel'
        citadel_name = extracted_city
        if not citadel_name:
            cit_match = re.search(r'([\w\s\'-]+?)\s+Citadel', orig, re.IGNORECASE)
            if cit_match:
                citadel_name = cit_match.group(1).strip()
                if citadel_name.upper() in ('SALVATION ARMY', 'THE SALVATION ARMY', ''):
                    citadel_name = None
        detail = citadel_name or city or 'Unknown'
        if detail.upper().endswith('CITADEL'):
            normalized = f"The Salvation Army — {detail}"
        else:
            normalized = f"The Salvation Army — {detail} Citadel"
    elif has_temple:
        sa_type = 'temple'
        temple_name = extracted_city
        if not temple_name:
            tm_match = re.search(r'([\w\s\'-]+?)\s+Temple', orig, re.IGNORECASE)
            if tm_match:
                temple_name = tm_match.group(1).strip()
                if temple_name.upper() in ('SALVATION ARMY', 'THE SALVATION ARMY', ''):
                    temple_name = None
        detail = temple_name or city or 'Unknown'
        if detail.upper().endswith('TEMPLE'):
            normalized = f"The Salvation Army — {detail}"
        else:
            normalized = f"The Salvation Army — {detail} Temple"
    elif has_hall:
        sa_type = 'hall'
        raw_detail = extracted_city or city or 'Unknown'
        # Avoid "Prayer Hall Hall" - strip type word from detail if already present
        detail = re.sub(r'\s+Hall$', '', raw_detail, flags=re.IGNORECASE).strip()
        if not detail:
            detail = raw_detail
        normalized = f"The Salvation Army — {detail} Hall"
    elif has_chapel:
        sa_type = 'chapel'
        raw_detail = extracted_city or city or 'Unknown'
        # Strip "Chapel" from start or end of detail
        detail = re.sub(r'^Chapel\s+', '', raw_detail, flags=re.IGNORECASE).strip()
        detail = re.sub(r'\s+Chapel$', '', detail, flags=re.IGNORECASE).strip()
        if not detail:
            detail = raw_detail
        normalized = f"The Salvation Army — {detail} Chapel"
    elif has_worship:
        sa_type = 'church'
        detail = extracted_city or city or 'Worship Center'
        normalized = f"The Salvation Army — {detail} Worship Center"
    elif has_community:
        sa_type = 'community_church'
        detail = extracted_city or city or 'Unknown'
        normalized = f"The Salvation Army — {detail} Community Church"
    elif has_church:
        sa_type = 'church'
        raw_detail = extracted_city or city or 'Unknown'
        detail = re.sub(r'\s+Church$', '', raw_detail, flags=re.IGNORECASE).strip()
        if not detail:
            detail = raw_detail
        normalized = f"The Salvation Army — {detail} Church"
    elif has_centre:
        sa_type = 'community_church'
        detail = extracted_city or city or 'Unknown'
        normalized = f"The Salvation Army — {detail} Centre"
    else:
        # Generic — just "Salvation Army" with no type keyword
        sa_type = 'generic'
        detail = extracted_city or city or ''
        if detail:
            normalized = f"The Salvation Army — {detail}"
        else:
            normalized = "The Salvation Army"
    
    return sa_type, detail, normalized, extracted_city


def progress_bar(current, total, label=''):
    """Simple progress bar."""
    if total == 0:
        return
    bar_len = 40
    filled = int(bar_len * current / total)
    bar = '█' * filled + '░' * (bar_len - filled)
    pct = current * 100 // total
    sys.stdout.write(f'\r  {bar} {pct}% | {label} [{current}/{total}]')
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write('\n')


def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print('🔷 DRY RUN MODE — no changes will be made\n')
    
    db_path = 'E:\\grid\\churches.db'
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    
    # ── Step 1: Find all SA entries ──
    print('🔍 Finding Salvation Army entries...')
    cur = db.execute("""
        SELECT id, name, city, state, country, latitude, longitude, 
               source, landmark_type, denomination_affiliation,
               family, subtradition, normalized_name
        FROM churches
        WHERE name LIKE '%Salvation Army%'
           OR name LIKE '%Armée du Salut%'
           OR name LIKE '%Heilsarmee%'
           OR name LIKE '%Frälsningsarmén%'
           OR name LIKE '%Frelsesarmeen%'
           OR name LIKE '%Pelastusarmeija%'
           OR name LIKE '%Ejército de Salvación%'
           OR name LIKE '%Exército de Salvação%'
           OR name LIKE '%Ejercito de Salvacion%'
           OR name LIKE '%Exercito de Salvacao%'
           OR name LIKE '%Armia Zbawienia%'
           OR denomination_affiliation LIKE '%Salvation Army%'
           OR subtradition LIKE '%Salvation%'
           OR family LIKE '%Salvation Army%'
        ORDER BY id
    """)
    rows = cur.fetchall()
    total = len(rows)
    print(f'  Found {total} Salvation Army entries\n')
    
    if total == 0:
        print('No entries found. Exiting.')
        db.close()
        return
    
    # ── Step 2: Analyze and classify all names ──
    print('📊 Classifying entries...')
    classifications = {}  # church_id -> (sa_type, detail, normalized, extracted_city)
    type_counts = {}
    lang_counts = {}
    
    for i, row in enumerate(rows):
        church_id = row['id']
        name = row['name'] or ''
        city = row['city'] or ''
        country = row['country'] or ''
        
        sa_type, detail, normalized, extracted_city = classify_sa_name(name, city, country)
        classifications[church_id] = (sa_type, detail, normalized, extracted_city)
        type_counts[sa_type] = type_counts.get(sa_type, 0) + 1
        
        # Language tracking
        low = name.lower()
        if 'heilsarmee' in low: lang_counts['German'] = lang_counts.get('German', 0) + 1
        if 'frälsningsarmén' in low or 'fralsningsarmen' in low: lang_counts['Swedish'] = lang_counts.get('Swedish', 0) + 1
        if 'frelsesarmeen' in low: lang_counts['Norwegian'] = lang_counts.get('Norwegian', 0) + 1
        if 'pelastusarmeija' in low: lang_counts['Finnish'] = lang_counts.get('Finnish', 0) + 1
        if 'armée du salut' in low or 'armee du salut' in low: lang_counts['French'] = lang_counts.get('French', 0) + 1
        if 'ejército de salvación' in low or 'ejercito de salvacion' in low: lang_counts['Spanish'] = lang_counts.get('Spanish', 0) + 1
        if 'exército de salvação' in low or 'exercito de salvacao' in low: lang_counts['Portuguese'] = lang_counts.get('Portuguese', 0) + 1
        if 'armia zbawienia' in low: lang_counts['Polish'] = lang_counts.get('Polish', 0) + 1
        
        progress_bar(i + 1, total, 'Classifying')
    
    print('\nType breakdown:')
    for t in sorted(type_counts, key=lambda x: -type_counts[x]):
        print(f'  {type_counts[t]:>6} | {t}')
    
    if lang_counts:
        print('\nLanguage variants:')
        for l in sorted(lang_counts, key=lambda x: -lang_counts[x]):
            print(f'  {lang_counts[l]:>6} | {l}')
    
    # ── Step 3: Create sa_hierarchy table ──
    print('\n🗄️  Creating sa_hierarchy table...')
    if not dry_run:
        # Drop if exists
        db.execute("DROP TABLE IF EXISTS sa_hierarchy")
        db.execute("""
            CREATE TABLE sa_hierarchy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id INTEGER REFERENCES sa_hierarchy(id),
                church_id INTEGER REFERENCES churches(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                original_name TEXT,
                sa_type TEXT NOT NULL CHECK(sa_type IN (
                    'corps', 'citadel', 'temple', 'hall', 'chapel',
                    'community_church', 'church', 'hq', 'social_service',
                    'school', 'musical_group', 'governing_council', 'generic', 'other'
                )),
                sa_detail TEXT,
                territory TEXT,
                division TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                lat REAL,
                lon REAL,
                parent_sa_type TEXT,
                relationship TEXT CHECK(relationship IN (
                    'headquartered_in',
                    'part_of',
                    'belongs_to_territory',
                    'affiliated_with'
                )),
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                CONSTRAINT unique_link UNIQUE(church_id, parent_id, relationship)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_sa_type ON sa_hierarchy(sa_type)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sa_country ON sa_hierarchy(country)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sa_church ON sa_hierarchy(church_id)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_sa_parent ON sa_hierarchy(parent_id)")
        print('  ✅ Table created')
    else:
        print('  ⏭️  Skipped (dry run)')
    
    # ── Step 4: Insert classification results ──
    print('\n📝 Inserting classification results...')
    insert_sql = """
        INSERT INTO sa_hierarchy (church_id, name, original_name, sa_type, sa_detail,
                                  city, state, country, lat, lon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    batch = []
    for i, row in enumerate(rows):
        church_id = row['id']
        name = row['name'] or ''
        city = row['city'] or ''
        state = row['state'] or ''
        country = row['country'] or ''
        lat = row['latitude']
        lon = row['longitude']
        
        sa_type, detail, normalized, extracted_city = classifications[church_id]
        
        batch.append((
            church_id, normalized, name, sa_type, detail,
            city, state, country, lat, lon
        ))
        
        if len(batch) >= CHUNK:
            if not dry_run:
                db.executemany(insert_sql, batch)
                db.commit()
            batch = []
        
        progress_bar(i + 1, total, 'Inserting')
    
    if batch:
        if not dry_run:
            db.executemany(insert_sql, batch)
            db.commit()
    
    if not dry_run:
        inserted = db.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]
        print(f'\n  ✅ {inserted} rows inserted')
    else:
        print(f'\n  ⏭️  Would insert {total} rows')
    
    # ── Step 5: Build hierarchy links ──
    print('\n🔗 Building hierarchy links...')
    
    if not dry_run:
        # 5a. Identify known HQs and link them
        hq_entries = db.execute("""
            SELECT id, church_id, city, state, country, sa_detail
            FROM sa_hierarchy
            WHERE sa_type = 'hq'
        """).fetchall()
        
        # 5b. Link corps/citadels/temples to their HQs by country
        # For now, link to the best-matching territorial/divisional HQ
        for hq in hq_entries:
            hq_id = hq['id']
            hq_country = hq['country']
            hq_city = (hq['city'] or '').lower()
            hq_detail = (hq['sa_detail'] or '').lower()
            
            # Find entries in the same country that might belong under this HQ
            subordinate_types = ('corps', 'citadel', 'temple', 'hall', 'chapel',
                                'church', 'community_church', 'generic')
            
            # Match by country + city if HQ has a city
            if hq_city:
                subordinates = db.execute("""
                    SELECT id, church_id, city, sa_type
                    FROM sa_hierarchy
                    WHERE sa_type IN ({})
                      AND country = ?
                      AND LOWER(city) = ?
                      AND parent_id IS NULL
                      AND id != ?
                """.format(','.join('?' * len(subordinate_types))),
                    subordinate_types + (hq_country, hq_city, hq_id)
                ).fetchall()
                
                for sub in subordinates:
                    db.execute("""
                        UPDATE sa_hierarchy
                        SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'part_of',
                            notes = 'Auto-linked by same city+country'
                        WHERE id = ?
                    """, (hq_id, sub['id']))
            
            # Also match territorial HQs to all entries in their country
            if 'territor' in hq_detail or 'territorial' in hq_detail:
                subordinates = db.execute("""
                    SELECT id FROM sa_hierarchy
                    WHERE country = ? AND id != ? AND parent_id IS NULL
                """, (hq_country, hq_id)).fetchall()
                
                for sub in subordinates:
                    db.execute("""
                        UPDATE sa_hierarchy
                        SET parent_id = ?, parent_sa_type = 'hq',
                            relationship = 'belongs_to_territory',
                            notes = 'Auto-linked by country to territorial HQ'
                        WHERE id = ?
                    """, (hq_id, sub['id']))
        
        db.commit()
        
        # Count links
        linked = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
        unlinked = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NULL").fetchone()[0]
        print(f'  ✅ {linked} entries linked to hierarchy, {unlinked} unlinked')
    
    # ── Step 6: Update churches table (denomination_affiliation, family, normalized_name) ──
    print('\n✏️  Updating churches table...')
    if not dry_run:
        update_sql = """
            UPDATE churches
            SET denomination_affiliation = 'The Salvation Army',
                family = CASE WHEN family IS NULL THEN 'Holiness Churches' ELSE family END,
                subtradition = CASE WHEN subtradition IS NULL THEN 'Salvationist' ELSE subtradition END
            WHERE id = ?
        """
        batch = []
        for i, row in enumerate(rows):
            batch.append((row['id'],))
            if len(batch) >= CHUNK:
                db.executemany(update_sql, batch)
                db.commit()
                batch = []
            progress_bar(i + 1, total, 'Updating churches')
        
        if batch:
            db.executemany(update_sql, batch)
            db.commit()
        print('  ✅ churches table updated')
    else:
        print('  ⏭️  Skipped (dry run)')
    
    # ── Step 7: Log provenance ──
    print('\n📜 Logging provenance...')
    if not dry_run:
        now = datetime.now().isoformat()
        prov_batch = []
        for i, row in enumerate(rows):
            sa_type, detail, normalized, _ = classifications[row['id']]
            prov_batch.append((
                row['id'],
                'sa_hierarchy_import',
                'classified',
                now,
                f'Type={sa_type}, Detail={detail}, Normalized={normalized}'
            ))
            if len(prov_batch) >= CHUNK:
                db.executemany("""
                    INSERT INTO provenance_log (church_id, source, action, timestamp, details)
                    VALUES (?, ?, ?, ?, ?)
                """, prov_batch)
                db.commit()
                prov_batch = []
            progress_bar(i + 1, total, 'Logging provenance')
        
        if prov_batch:
            db.executemany("""
                INSERT INTO provenance_log (church_id, source, action, timestamp, details)
                VALUES (?, ?, ?, ?, ?)
            """, prov_batch)
            db.commit()
        print('  ✅ Provenance logged')
    
    # ── Summary ──
    print('\n' + '=' * 60)
    print('📋 SUMMARY')
    print('=' * 60)
    print(f'  Total SA entries processed: {total}')
    print(f'  Type breakdown:')
    for t in sorted(type_counts, key=lambda x: -type_counts[x]):
        print(f'    {type_counts[t]:>6} | {t}')
    
    if not dry_run:
        linked = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
        hq_count = db.execute("SELECT COUNT(*) FROM sa_hierarchy WHERE sa_type='hq'").fetchone()[0]
        print(f'\n  Hierarchy links created: {linked}')
        print(f'  HQ entries identified: {hq_count}')
        print(f'  Table: sa_hierarchy ({db.execute("SELECT COUNT(*) FROM sa_hierarchy").fetchone()[0]} rows)')
    
    print(f'\n  ✅ Done!')
    if dry_run:
        print('  (Dry run — no changes committed)')
    
    db.close()


if __name__ == '__main__':
    main()

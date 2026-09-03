"""
Extract city names from church names for US records missing city.
Uses known US city→state mappings from existing churches to validate.

Patterns tried (in priority order):
  1. "OF <CITY>" at end of name
  2. Standalone city name match against known US cities in same state

Usage:
  python scripts/enrichment/extract_city_from_name.py --dry-run
  python scripts/enrichment/extract_city_from_name.py
  python scripts/enrichment/extract_city_from_name.py --limit 100
"""
import sqlite3, sys, os, re, time, collections

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')

DRY_RUN = '--dry-run' in sys.argv
APPLY = '--apply' in sys.argv
LIMIT = None
for i, a in enumerate(sys.argv):
    if a.startswith('--limit='):
        LIMIT = int(a.split('=')[1])
    elif a == '--limit' and i + 1 < len(sys.argv):
        LIMIT = int(sys.argv[i + 1])

# ── Garbage name patterns to skip entirely ──
GARBAGE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^CHURCH HEALTH$',
        r'^CHURCH SECURITY$',
        r'^ANNUAL CHURCH PROFILE',
        r'^ACP\b',
        r'^CHURCH PLANTING',
        r'^CHURCH PLANT\b',
        r'^CHURCH GROWTH',
        r'^CHURCH ADMIN',
        r'^CHURCH OFFICE',
        r'^CHURCH SURVEY',
        r'^CHURCH STATS',
        r'^CHURCH REPORT',
        r'^CHURCH DIRECTORY',
        r'^CHURCH DIRECTORY',
        r'^SUNDAY SCHOOL',
        r'^BIBLE STUDY',
        r'^YOUTH GROUP',
        r'^YOUTH MINISTRY',
        r'^CHILDREN',
        r'^KIDS MINISTRY',
        r'^WORSHIP TEAM',
        r'^PRAISE TEAM',
        r'^CHURCH STAFF',
        r'^PASTOR\b',
        r'^REVEREND\b',
        r'^MINISTER\b',
        r'^BISHOP\b',
        r'^ELDER\b',
        r'^DEACON\b',
        r'^TRUSTEE\b',
        r'^MISSIONARY\b',
        r'^EVANGELIST\b',
    ]
]

def is_garbage(name):
    if not name:
        return True
    name = name.strip()
    for pat in GARBAGE_PATTERNS:
        if pat.match(name):
            return True
    return False

# ── Load known US cities from churches ──
print("Loading known US city -> state mappings...")
db = sqlite3.connect(DB)
c = db.cursor()

c.execute("""
    SELECT UPPER(city), state, COUNT(*) as n
    FROM churches
    WHERE country='US' AND city IS NOT NULL AND city != ''
      AND state IS NOT NULL AND state != ''
    GROUP BY UPPER(city), state
    ORDER BY n DESC
""")
city_state_count = {}
state_cities = collections.defaultdict(set)
all_cities = set()
for city_upper, state, n in c.fetchall():
    city_state_count[(city_upper, state)] = n
    if city_upper not in city_state_count or city_state_count.get((city_upper, state), 0) > city_state_count.get((city_upper, '__total__'), 0):
        pass
    state_cities[state].add(city_upper)
    all_cities.add(city_upper)
    # Track most common state for each city
    prev = city_state_count.get((city_upper, '__total__'), 0)
    city_state_count[(city_upper, '__total__')] = prev + n

# Most common state per city
city_best_state = {}
for (city, state), n in city_state_count.items():
    if state == '__total__':
        continue
    if city not in city_best_state or n > city_best_state[city][1]:
        city_best_state[city] = (state, n)

print(f"  {len(all_cities):,} unique US city names across {len(state_cities)} states")

# ── Common false-positive city names (words that look like cities but aren't) ──
NOT_CITIES = {
    'CHURCH', 'CHAPEL', 'MINISTRY', 'MINISTRIES', 'FELLOWSHIP', 'WORSHIP',
    'TEMPLE', 'TABERNACLE', 'CATHEDRAL', 'PARISH', 'DIOCESE', 'SYNOD',
    'BAPTIST', 'METHODIST', 'LUTHERAN', 'PRESBYTERIAN', 'CATHOLIC', 'EPISCOPAL',
    'PENTECOSTAL', 'EVANGELICAL', 'APOSTOLIC', 'ORTHODOX', 'REFORMED',
    'CONGREGATIONAL', 'WESLEYAN', 'NAZARENE', 'MENNONITE', 'BRETHREN',
    'COMMUNITY', 'FAMILY', 'FAITH', 'GRACE', 'HOPE', 'LOVE', 'PEACE', 'JOY',
    'TRINITY', 'CALVARY', 'EMMANUEL', 'BETHEL', 'ZION', 'SHILOH', 'EBENEZER',
    'BEREAN', 'ANTIOCH', 'CORINTH', 'EPHESUS', 'GALILEE', 'BETHANY', 'BETHEL',
    'CARMEL', 'HERMON', 'MORIAH', 'OLIVET', 'PISGAH', 'SINAI', 'TABOR',
    'CHRIST', 'JESUS', 'GOD', 'LORD', 'SAVIOR', 'REDEEMER', 'MESSIAH',
    'FIRST', 'SECOND', 'THIRD', 'NEW', 'OLD', 'GREATER', 'LITTLE', 'BIG',
    'MOUNT', 'MOUNTAIN', 'VALLEY', 'RIVER', 'LAKE', 'OCEAN', 'HARBOR',
    'EAST', 'WEST', 'NORTH', 'SOUTH', 'CENTRAL', 'UNION', 'UNITED',
    'FREE', 'INDEPENDENT', 'PILGRIM', 'PILGRIMAGE', 'PIONEER', 'HERITAGE',
    'MEMORIAL', 'VICTORY', 'TRIUMPH', 'KINGDOM', 'HEAVEN', 'PARADISE',
    'CROSS', 'CROSSROADS', 'CORNERSTONE', 'ROCK', 'LIGHTHOUSE', 'SANCTUARY',
    'CHAPEL', 'ABBEY', 'MONASTERY', 'CONVENT', 'SEMINARY', 'INSTITUTE',
    'COLLEGE', 'UNIVERSITY', 'ACADEMY', 'SCHOOL',
    'STREET', 'AVENUE', 'ROAD', 'LANE', 'DRIVE', 'BOULEVARD', 'HIGHWAY',
    'CITIES', 'CITY', 'TOWN', 'VILLAGE', 'COUNTY',
    'ASSEMBLY', 'ASSEMBLIES', 'CONGREGATION', 'CONFERENCE', 'COUNCIL',
    'MISSION', 'MISSIONS', 'OUTREACH', 'CAMP', 'RETREAT', 'RANCH',
    'HOME', 'HOUSE', 'BUILDING', 'CENTER', 'CENTRE', 'HALL', 'AUDITORIUM',
    'INTERNATIONAL', 'WORLD', 'GLOBAL', 'NATION', 'NATIONAL',
    'LIFE', 'LIVING', 'LIGHT', 'TRUTH', 'WAY', 'PATH', 'GATE', 'DOOR',
    'SPRING', 'SPRINGS', 'WELL', 'FOUNTAIN', 'GARDEN', 'GROVE', 'PARK',
    'PRAISE', 'GLORY', 'HONOR', 'POWER', 'SPIRIT', 'PRESENCE',
    'BIBLE', 'GOSPEL', 'WORD', 'SCRIPTURE', 'TESTAMENT',
    'COVENANT', 'PROMISE', 'BLESSING', 'HARVEST', 'VINEYARD', 'VINE',
    'BRANCH', 'ROOT', 'SEED', 'TREE', 'OAK', 'CEDAR', 'PALM', 'OLIVE',
    'CORNER', 'STONE', 'FOUNDATION', 'BRIDGE', 'GATEWAY', 'PORTAL',
    'HILL', 'HILLS', 'RIDGE', 'PRAIRIE', 'MEADOW', 'FIELD', 'FOREST',
    'WOODS', 'CREEK', 'BROOK', 'RUN', 'FALLS', 'FORD', 'CROSSING',
    'DALE', 'GLEN', 'HOLLOW', 'KNOLL', 'BLUFF', 'CLIFF', 'PEAK',
    'ISLAND', 'ISLE', 'BEACH', 'SHORE', 'COAST', 'BAY', 'COVE', 'INLET',
    'VIEW', 'VISTA', 'OVERLOOK', 'HEIGHTS', 'SUMMIT', 'CREST', 'PASS',
    'TRAIL', 'PATHWAY', 'WALK', 'JOURNEY', 'TRAVEL', 'PILGRIMAGE',
    'REST', 'RESTORATION', 'RENEWAL', 'REVIVAL', 'REFUGE', 'SHELTER',
    'HAVEN', 'HARBOR', 'ANCHOR', 'COMPASS', 'BEACON', 'TORCH', 'FLAME',
    'FIRE', 'WIND', 'RAIN', 'STORM', 'THUNDER', 'LIGHTNING', 'CLOUD',
    'DESERT', 'WILDERNESS', 'OASIS', 'STREAM', 'FLOWING', 'WATER',
    'RISING', 'ASCEND', 'ASCENSION', 'RESURRECTION', 'TRANSFIGURATION',
    # Extra: common words that happen to be tiny hamlet names but aren't useful city signals
    'CAMPUS', 'CENTURY', 'FRANCIS', 'POND',
    # Common saint names that overlap with city names
    'LUKE', 'JOHN', 'MARK', 'PAUL', 'PETER', 'JAMES', 'ANDREW', 'THOMAS',
    'JEROME', 'AUGUSTINE', 'ANTHONY', 'JOSEPH', 'MARY', 'MICHAEL', 'GABRIEL',
    'PATRICK', 'STEPHEN', 'LAWRENCE', 'VINCENT', 'MARTIN', 'NICHOLAS',
    'CATHERINE', 'THERESA', 'ANNE', 'ROSE', 'CLARE', 'CECILIA', 'AGNES',
    'MONICA', 'HELENA', 'BERNADETTE', 'BRIGID', 'GERTRUDE', 'RITA',
    'FRANCIS', 'DOMINIC', 'BENEDICT', 'BERNARD', 'IGNATIUS', 'XAVIER',
    'LOUIS', 'CHARLES', 'EDWARD', 'GEORGE', 'HENRY', 'LEO', 'GREGORY',
    'CAMILLUS', 'STAR',  # "Star of the Sea" is a Marian title
    'ASSUMPTION',  # Marian dogma
    'SCOTLAND', 'ENGLAND', 'IRELAND', 'FRANCE',  # Countries in saint titles
}

# Regex to detect saint-prefixed names
SAINT_PREFIX = re.compile(r'^(SAINT|ST\.?)\b', re.IGNORECASE)

# Words that, when they follow a potential city word, disqualify it
# e.g., "BOYD AVENUE" → Boyd is a street name, not a city
STREET_CONTEXT_AFTER = {
    'AVENUE', 'AVE', 'STREET', 'ST', 'ROAD', 'RD', 'DRIVE', 'DR',
    'BOULEVARD', 'BLVD', 'LANE', 'LN', 'HIGHWAY', 'HWY', 'PARKWAY',
    'PLACE', 'PL', 'COURT', 'CT', 'CIRCLE', 'CIR', 'TERRACE', 'TER',
    'CREEK', 'RIVER', 'LAKE', 'HILL', 'MOUNTAIN', 'MT',
    'TRAIL', 'WAY', 'PATH', 'CROSSING', 'FORD', 'BEND',
    'PARK', 'PLAZA', 'SQUARE', 'MALL', 'PIKE',
}

def is_legit_city(word, state=None):
    """Check if word could be a city name. Returns (is_city, matches_state)."""
    w_upper = word.upper()
    if w_upper in NOT_CITIES:
        return False, False
    if w_upper not in all_cities:
        return False, False
    if state and state in state_cities:
        return True, w_upper in state_cities[state]
    return True, False

def get_best_state(city_upper):
    """Get the most common state for a city."""
    info = city_best_state.get(city_upper)
    return info[0] if info else None

# ── Patterns for extracting city from name ──
OF_PATTERN = re.compile(r'\bOF\s+([A-Z][A-Z\s\-\']+)$', re.IGNORECASE)
IN_PATTERN = re.compile(r'\bIN\s+([A-Z][A-Z\s\-\']+)$', re.IGNORECASE)
AT_PATTERN = re.compile(r'\bAT\s+([A-Z][A-Z\s\-\']+)$', re.IGNORECASE)

def extract_city_from_name(name, state=None):
    """Try to extract a city name from church name. Returns (city, new_state, confidence, method)."""
    if not name:
        return None, None, 0, None
    name = name.strip()
    
    # Helper: try a candidate city word
    def try_city(candidate_str):
        cand = candidate_str.strip().upper()
        if not cand:
            return None, None, 0, None
        
        is_city, matches_state = is_legit_city(cand, state)
        if not is_city:
            # Try individual words of multi-word (e.g., "FORT WORTH" → "FORT")
            words = cand.split()
            for w in words:
                is_c, matches_s = is_legit_city(w, state)
                if is_c:
                    if matches_s:
                        return w.title(), state, 0.55, 'partial_multiworld_state'
                    else:
                        best_st = get_best_state(w)
                        cc = city_state_count.get((w, best_st), 0) if best_st else 0
                        if cc >= 5:
                            return w.title(), best_st, 0.40, 'partial_multiworld_any'
            return None, None, 0, None
        
        if matches_state:
            return cand.title(), state, 0.85, 'state_match'
        else:
            best_st = get_best_state(cand)
            cc = city_state_count.get((cand, best_st), 0) if best_st else 0
            if cc >= 5:
                return cand.title(), best_st, 0.70, 'any_state'
            elif cc >= 2:
                return cand.title(), best_st, 0.55, 'any_state_weak'
            return None, None, 0, None
    
    # Try "OF <CITY>" pattern
    m = OF_PATTERN.search(name)
    if m:
        city, new_st, conf, method = try_city(m.group(1).strip())
        if city:
            return city, new_st, conf, f'of_{method}'
    
    # Try "IN <CITY>" pattern
    m = IN_PATTERN.search(name)
    if m:
        city, new_st, conf, method = try_city(m.group(1).strip())
        if city:
            return city, new_st, conf, f'in_{method}'
    
    # Try "AT <CITY>" pattern
    m = AT_PATTERN.search(name)
    if m:
        city, new_st, conf, method = try_city(m.group(1).strip())
        if city:
            return city, new_st, conf, f'at_{method}'
    
    # Try standalone city word match
    # Remove common suffixes from end first
    cleaned = name.upper()
    for suffix in [' BAPTIST CHURCH', ' METHODIST CHURCH', ' LUTHERAN CHURCH',
                   ' PRESBYTERIAN CHURCH', ' CATHOLIC CHURCH', ' EPISCOPAL CHURCH',
                   ' PENTECOSTAL CHURCH', ' COMMUNITY CHURCH', ' FAMILY CHURCH',
                   ' BIBLE CHURCH', ' GOSPEL CHURCH', ' CHRISTIAN CHURCH',
                   ' UNITED METHODIST CHURCH', ' UNITED CHURCH OF CHRIST',
                   ' ASSEMBLY OF GOD', ' CHURCH OF GOD', ' CHURCH OF CHRIST',
                   ' SEVENTH DAY ADVENTIST', ' JEHOVAH WITNESS',
                   ' CHRISTIAN FELLOWSHIP', ' CHRISTIAN CENTER',
                   ' WORSHIP CENTER', ' WORSHIP CENTRE', ' PRAYER CENTER',
                   ' REVIVAL CENTER', ' FAITH CENTER', ' LIFE CENTER',
                   ' CHRISTIAN ASSEMBLY', ' CHRISTIAN CHAPEL',
                   ' FULL GOSPEL', ' FOURSQUARE', ' VINEYARD',
                   ' CAMPUS', ' CAMP', ' CENTER', ' CENTRE',
                   ' CHURCH', ' CHAPEL', ' MINISTRY', ' MINISTRIES', ' FELLOWSHIP',
                   ' WORSHIP', ' TEMPLE', ' TABERNACLE', ' CATHEDRAL']:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
    
    # Split into words and look for city matches
    words = cleaned.split()
    candidates = []  # (word, matches_state, best_state, church_count)
    for i, w in enumerate(words):
        w = w.strip("',.()[]{}!?#")
        if not w or len(w) < 2:
            continue
        
        # Check street context: if next word is a street suffix, this isn't a city
        if i + 1 < len(words) and words[i + 1].upper().strip("',.()[]{}!?#") in STREET_CONTEXT_AFTER:
            continue
        # Check if this word itself is a street suffix
        if w in STREET_CONTEXT_AFTER:
            continue
        
        is_city, matches_state = is_legit_city(w, state)
        if is_city:
            best_st = get_best_state(w) if not matches_state else state
            # Get church count for this city in its best state
            cc = city_state_count.get((w, best_st), 0) if best_st else 0
            candidates.append((w, matches_state, best_st, cc))
    
    if candidates:
        # Prefer state-matching candidates, then last position
        state_matches = [c for c in candidates if c[1]]
        if state_matches:
            c = state_matches[-1]
            return c[0].title(), c[2], 0.65, 'word_state_match'
        else:
            # For any_state matches, require city to have ≥5 churches (filter tiny hamlets)
            solid = [c for c in candidates if c[3] >= 5]
            if solid:
                c = solid[-1]
                return c[0].title(), c[2], 0.50, 'word_any_state'
            # If no solid match, still try if it's a unique word (only 1 candidate)
            elif len(candidates) == 1 and candidates[0][3] >= 2:
                c = candidates[0]
                return c[0].title(), c[2], 0.40, 'word_any_state_weak'
    
    return None, None, 0, None


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    # ── Fetch records ──
    print("\nFetching US records missing city...")
    sql = """
        SELECT id, name, state, source
        FROM churches
        WHERE country='US' AND (city IS NULL OR city='')
        ORDER BY id
    """
    if LIMIT:
        sql += f' LIMIT {LIMIT}'

    rows = c.execute(sql).fetchall()
    total = len(rows)
    print(f"  {total:,} records to process")

    # ── Process ──
    results = []
    garbage_count = 0
    extracted = 0
    no_match = 0

    for row in rows:
        church_id, name, state, source = row
        
        if is_garbage(name):
            garbage_count += 1
            if DRY_RUN:
                print(f"  GARBAGE [{church_id}] {(name or 'N/A')[:50]}")
            continue
        
        city, new_state, confidence, method = extract_city_from_name(name, state)
        
        if city:
            extracted += 1
            st_info = f" -> {state}" if new_state == state else f" [st: {state}->{new_state}]"
            results.append((church_id, city, state, new_state, confidence, method))
            if DRY_RUN:
                print(f"  OK [{church_id}] {(name or 'N/A')[:40]} -> {city}{st_info} ({method}, {confidence:.0%})")
        else:
            no_match += 1
            if DRY_RUN:
                print(f"  NO [{church_id}] {(name or 'N/A')[:55]} | {state}")

    print(f"\n{'DRY RUN - ' if DRY_RUN else ''}Results:")
    print(f"  Garbage: {garbage_count:,}")
    print(f"  Extracted: {extracted:,} ({100*extracted/total:.1f}%)")
    print(f"  No match: {no_match:,} ({100*no_match/total:.1f}%)")

    if not DRY_RUN and APPLY and results:
        # ── Apply ──
        print(f"\nApplying {len(results):,} city names...")
        script_name = 'extract_city_from_name'
        started = time.strftime('%Y-%m-%d %H:%M:%S')
        
        chunk_size = 500
        applied = 0
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i+chunk_size]
            for church_id, city, old_state, new_state, confidence, method in chunk:
                c.execute("""
                    UPDATE churches SET city=?, last_updated=datetime('now')
                    WHERE id=?
                """, (city, church_id))
                c.execute("""
                    INSERT INTO enrichment_change_log 
                    (church_id, field_name, old_value, new_value, change_source, changed_at)
                    VALUES (?, 'city', NULL, ?, ?, datetime('now'))
                """, (church_id, city, f'{script_name}:{method}:{confidence:.2f}'))
                # Also fix state if it changed
                if new_state and new_state != old_state:
                    c.execute("""
                        UPDATE churches SET state=?, last_updated=datetime('now')
                        WHERE id=?
                    """, (new_state, church_id))
                    c.execute("""
                        INSERT INTO enrichment_change_log 
                        (church_id, field_name, old_value, new_value, change_source, changed_at)
                        VALUES (?, 'state', ?, ?, ?, datetime('now'))
                    """, (church_id, old_state, new_state, f'{script_name}:state_correction:{confidence:.2f}'))
                applied += 1
            db.commit()
            print(f"  {applied}/{len(results)} committed...", end='\r')
        
        # ── Provenance ──
        c.execute("""
            INSERT INTO provenance_log 
            (source, script_name, started_at, completed_at, churches_updated, 
             fields_populated, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            script_name, script_name, started,
            time.strftime('%Y-%m-%d %H:%M:%S'), applied,
            'city', 'completed',
            f'Extracted city from church name. {garbage_count} garbage skipped, {no_match} no match.'
        ))
        db.commit()
        
        print(f"\n  Applied: {applied:,}")
        print(f"  Provenance logged")
    else:
        print("\nUse --apply to write changes. Dry run only.")

    db.close()
    print("Done.")

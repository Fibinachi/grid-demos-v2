"""
VERMONT CLEANUP ROUND 3 — Final fixes for all remaining odd cities.
"""
import sqlite3, re

db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

# Comprehensive VT town list (all incorporated towns + major villages)
VT_TOWNS = {
    'ADDISON','ALBANY','ALBURGH','ANDOVER','ARLINGTON','ATHENS','AVERILL','BAKERSFIELD',
    'BALTIMORE','BARNARD','BARNET','BARRE','BARTON','BELVIDERE','BENNINGTON','BENSON',
    'BERKSHIRE','BERLIN','BETHEL','BLOOMFIELD','BOLTON','BRADFORD','BRAINTREE','BRANDON',
    'BRATTLEBORO','BRIDGEWATER','BRIDPORT','BRIGHTON','BRISTOL','BROOKFIELD','BROOKLINE',
    'BROWNINGTON','BRUNSWICK','BURKE','BURLINGTON','CABOT','CALAIS','CAMBRIDGE','CANAAN',
    'CASTLETON','CAVENDISH','CHARLESTON','CHARLOTTE','CHELSEA','CHESTER','CHITTENDEN',
    'CLARENDON','COLCHESTER','CONCORD','CORINTH','CORNISH','COVENTRY','CRAFTSBURY',
    'DANBY','DANVILLE','DERBY','DORSET','DOVER','DUMMERSTON','DUXBURY','EAST HAVEN',
    'EAST MONTPELIER','EDEN','ELMORE','ENOSBURG','ESSEX','FAIR HAVEN','FAIRFAX','FAIRFIELD',
    'FAIRLEE','FAYSTON','FERDINAND','FERRISBURGH','FLETCHER','FRANKLIN','GEORGIA',
    'GLOVER','GOSHEN','GRAFTON','GRAND ISLE','GRANVILLE','GREENSBORO','GROTON','GUILDHALL',
    'GUILFORD','HALIFAX','HANCOCK','HARDWICK','HARTFORD','HARTLAND','HIGHGATE','HINESBURG',
    'HOLLAND','HUBBARDTON','HUNTINGTON','HYDE PARK','IRA','IRASBURG','ISLE LA MOTTE',
    'JAMAICA','JAY','JERICHO','JOHNSON','KILLINGTON','KIRBY','LANDGROVE','LEICESTER',
    'LEMINGTON','LEWIS','LINCOLN','LONDONDERRY','LOWELL','LUDLOW','LUNENBURG','LYNDON',
    'MAIDSTONE','MANCHESTER','MARLBORO','MARSHFIELD','MENDON','MIDDLEBURY','MIDDLESEX',
    'MIDDLETOWN SPRINGS','MILTON','MONKTON','MONTGOMERY','MONTPELIER','MORETOWN','MORGAN',
    'MORRISTOWN','MOUNT HOLLY','MOUNT TABOR','NEW HAVEN','NEWARK','NEWBURY','NEWFANE',
    'NEWPORT','NORTH HERO','NORTHFIELD','NORTON','NORWICH','ORANGE','ORLEANS','ORWELL',
    'PANTON','PAWLET','PEACHAM','PITTSFIELD','PITTSFORD','PLAINFIELD','PLYMOUTH','POMFRET',
    'POULTNEY','POWNAL','PROCTOR','PUTNEY','RANDOLPH','READING','READSBORO','RICHFORD',
    'RICHMOND','RIPTON','ROCHESTER','ROCKINGHAM','ROXBURY','ROYALTON','RUPERT','RUTLAND',
    'RYEGATE','SALISBURY','SANDGATE','SEARSBURG','SHAFTSBURY','SHARON','SHEFFIELD',
    'SHELBURNE','SHELDON','SHOREHAM','SHREWSBURY','SOMERSET','SOUTH BURLINGTON',
    'SOUTH HERO','SPRINGFIELD','ST ALBANS','ST GEORGE','ST JOHNSBURY','STAMFORD','STANNARD',
    'STARKSBORO','STOCKBRIDGE','STOWE','STRAFFORD','STRATTON','SUDBURY','SUNDERLAND',
    'SUTTON','SWANTON','THETFORD','TINMOUTH','TOPSHAM','TOWNSHEND','TROY','TUNBRIDGE',
    'UNDERHILL','VERGENNES','VERSHIRE','VICTORY','WAITSFIELD','WALDEN','WALLINGFORD',
    'WALTHAM','WARDSBORO','WARREN','WASHINGTON','WATERBURY','WATERFORD','WATERVILLE',
    'WEATHERSFIELD','WELLS','WEST FAIRLEE','WEST HAVEN','WEST RUTLAND','WEST WINDSOR',
    'WESTFIELD','WESTFORD','WESTMINSTER','WESTMORE','WESTON','WEYBRIDGE','WHEELOCK',
    'WHITING','WHITINGHAM','WILLIAMSTOWN','WILLISTON','WILMINGTON','WINDHAM','WINDSOR',
    'WINHALL','WINOOSKI','WOLCOTT','WOODBURY','WOODFORD','WOODSTOCK','WORCESTER',
    # Major villages/neighborhoods
    'PROCTORSVILLE','ESSEX JUNCTION','WHITE RIVER JUNCTION','JEFFERSONVILLE',
    'MANCHESTER CENTER','SOUTH ROYALTON','BELLOWS FALLS','LYNDONVILLE',
    'WEST BURKE','EAST BURKE','JACKSONVILLE','WILDER',
}

VT_TOWNS_UPPER = {t.upper() for t in VT_TOWNS}

def extract_vt_town(name):
    """Extract a VT town name from a church/organization name."""
    if not name:
        return None
    name_upper = name.upper()
    
    # Sort by length (longest first) to match multi-word towns first
    sorted_towns = sorted(VT_TOWNS_UPPER, key=len, reverse=True)
    
    for town in sorted_towns:
        if town in name_upper:
            idx = name_upper.find(town)
            # Check word boundaries
            before_ok = idx == 0 or not name_upper[idx-1].isalpha()
            after_ok = idx + len(town) >= len(name_upper) or not name_upper[idx+len(town)].isalpha()
            if before_ok and after_ok:
                # Don't match very common words that aren't town names in context
                if town in ('ESSEX','WASHINGTON','FRANKLIN','ORANGE','WARREN','LINCOLN',
                           'VICTORY','READING','HOLLAND','BERKSHIRE'):
                    # Only match if at end or followed by common suffixes
                    remaining = name_upper[idx+len(town):].strip()
                    if remaining and not remaining.startswith(('COUNTY',' CO',' ST')):
                        continue
                return town.title()
    return None

# ============================================================
# PHASE 1: Delete Kōchi garbage (all are blog/news scraped content)
# ============================================================
print("=== PHASE 1: Delete Kōchi records ===")
n = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND city='Kōchi'").fetchone()['n']
db.execute("DELETE FROM churches WHERE state='VT' AND country='US' AND city='Kōchi'")
db.commit()
print(f'  Deleted {n} Kōchi records')

# ============================================================
# PHASE 2: Fix Kitakyūshū — extract town from name
# ============================================================
print("\n=== PHASE 2: Fix Kitakyūshū records ===")
kit_records = db.execute("""
    SELECT id, name FROM churches 
    WHERE state='VT' AND country='US' AND city='Kitakyūshū'
""").fetchall()

updates = []
garbage = []
for r in kit_records:
    town = extract_vt_town(r['name'])
    if town:
        updates.append((town, r['id']))
    else:
        # Check if this is garbage
        name = r['name'].upper() if r['name'] else ''
        garbage_patterns = ['CULTURE DAY','ENROLLMENT','GRADUATION','CELEBRATION',
                          'ANNIVERSARY','NEWMAN CONFERENCE','CLOSES AFTER','BIBLE 3',
                          'BIBLE 4',' I KNEW','CRAFT FAIR','WARMING SHELTER',
                          'PEACE CORPS','INCREASES','ACCREDITATION']
        is_garbage = any(p in name for p in garbage_patterns)
        if is_garbage:
            garbage.append(r['id'])
        else:
            # Real church but couldn't extract town — NULL the city
            updates.append((None, r['id']))

if updates:
    db.executemany("UPDATE churches SET city=? WHERE id=?", updates)
if garbage:
    placeholders = ','.join(['?']*len(garbage))
    db.execute(f"DELETE FROM churches WHERE id IN ({placeholders})", garbage)
db.commit()
print(f'  Fixed: {len(updates)}, Deleted garbage: {len(garbage)}')

# ============================================================
# PHASE 3: Fix remaining Amchitka — name-based town extraction
# ============================================================
print("\n=== PHASE 3: Fix remaining Amchitka ===")
am_records = db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka'
""").fetchall()

am_updates = []
for r in am_records:
    town = extract_vt_town(r['name'])
    if town:
        am_updates.append((town, r['id']))

if am_updates:
    db.executemany("UPDATE churches SET city=? WHERE id=?", am_updates)
    db.commit()
print(f'  Name-based fixes: {len(am_updates)}/{len(am_records)}')

remaining_am = db.execute("""
    SELECT COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city='Amchitka'
""").fetchone()['n']
if remaining_am > 0:
    # For the truly unfixable, NULL the city
    db.execute("UPDATE churches SET city=NULL WHERE state='VT' AND country='US' AND city='Amchitka'")
    db.commit()
    print(f'  NULLed remaining {remaining_am} Amchitka records (no town in name)')

# ============================================================
# PHASE 4: Fix remaining Istanbul — name-based + spatial
# ============================================================
print("\n=== PHASE 4: Fix remaining Istanbul ===")
ist_records = db.execute("""
    SELECT id, name, latitude, longitude FROM churches 
    WHERE state='VT' AND country='US' AND city='Istanbul'
""").fetchall()

ist_updates = []
for r in ist_records:
    town = extract_vt_town(r['name'])
    if town:
        ist_updates.append((town, r['id']))
    else:
        ist_updates.append((None, r['id']))

if ist_updates:
    db.executemany("UPDATE churches SET city=? WHERE id=?", ist_updates)
    db.commit()
print(f'  Fixed: {len([u for u in ist_updates if u[0]])}, NULLed: {len([u for u in ist_updates if not u[0]])}')

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "="*60)
print("FINAL VERMONT SUMMARY (after cleanup round 3)")
print("="*60)

total = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US'").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND latitude IS NOT NULL").fetchone()['n']

print(f'Total VT churches: {total:,}')
print(f'GPS coverage: {gps:,} ({100*gps//total}%)')

print('\nFaith Breakdown:')
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r["faith"]}: {r["n"]:,}')

print('\nTop 20 Cities:')
for r in db.execute("SELECT city, COUNT(*) as n FROM churches WHERE state='VT' AND country='US' GROUP BY city ORDER BY n DESC LIMIT 20"):
    display = r['city'] if r['city'] else '(NULL)'
    print(f'  {display}: {r["n"]:,}')

print('\nTop 20 Traditions:')
for r in db.execute("""
    SELECT tradition, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND tradition IS NOT NULL 
    GROUP BY tradition ORDER BY n DESC LIMIT 20
"""):
    print(f'  {r["tradition"]}: {r["n"]:,}')

print('\nContact Coverage:')
for r in db.execute('''
    SELECT contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv
    JOIN churches c ON c.id = cv.church_id
    WHERE c.state='VT' AND c.country='US'
    GROUP BY contact_type
'''):
    print(f'  {r["contact_type"]}: {r["n"]:,}')

# Check remaining odd cities
odd = ['Istanbul','Amchitka','Fukuoka','Matsuyama','Shimonoseki','Takamatsu','Tokushima','Kochi','Kōchi','Kitakyūshū']
odd_rem = db.execute(f"""
    SELECT city, COUNT(*) as n FROM churches 
    WHERE state='VT' AND country='US' AND city IN ({','.join(['?']*len(odd))})
    GROUP BY city
""", odd).fetchall()
if odd_rem:
    print(f'\n⚠ Remaining odd: {sum(r["n"] for r in odd_rem)}')
    for r in odd_rem:
        print(f'  {r["city"]}: {r["n"]}')
else:
    print('\n✅ ALL odd city names CLEANED!')

# County
null_cty = db.execute("SELECT COUNT(*) as n FROM churches WHERE state='VT' AND country='US' AND (county IS NULL OR county='')").fetchone()['n']
print(f'\nNULL county: {null_cty:,}/{total:,}')

db.close()
print("\n✅ Vermont cleanup complete!")

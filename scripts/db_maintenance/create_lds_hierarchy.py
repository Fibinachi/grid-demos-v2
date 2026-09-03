"""
Create the lds_hierarchy table and populate it from churches data.

LDS organizational structure — buildings are the physical assets,
everything else is a ministry stored as JSON.

Building types:
  hq                  World HQ (Church Office Building, SLC)
  area_office         Area office building (regional admin)
  temple              Temple (sacred building)
  mission_office      Mission office
  stake_house         Building hosting stake functions
  meetinghouse        Building hosting wards/branches
  institute           Institute of Religion (CES)
  seminary            Seminary (CES)
  storehouse          Bishop's Storehouse (Welfare)
  employment_center   Employment Center
  family_history_center Family History Center

Hierarchy:
  HQ → Area Office → Temple → Stake House → Meetinghouse
  HQ → Institute / Seminary / Storehouse / etc. (direct)

Usage:
    python scripts/db_maintenance/create_lds_hierarchy.py
    python scripts/db_maintenance/create_lds_hierarchy.py --dry-run
"""
import sqlite3, json, re, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

def normalize(s):
    if s is None: return ''
    return s.strip().lower()

# LDS matching WHERE clause
# Uses word-boundary patterns to avoid false matches like "brickfields"→"LDS"
lds_where = """
    (denomination = 'The Church of Jesus Christ of Latter-day Saints'
     OR name LIKE '%Church of Jesus Christ of Latter%-day Saint%'
     OR name LIKE '%Latter%-day Saint%'
     OR (name LIKE '% LDS %' OR name LIKE 'LDS %' OR name LIKE '% LDS' OR name = 'LDS'
         OR name LIKE '% Lds %' OR name LIKE 'Lds %' OR name LIKE '% Lds' OR name = 'Lds'
         OR name LIKE '% Lds' OR name LIKE 'Lds%')
     OR (name LIKE '% Mormon %' OR name LIKE 'Mormon %' OR name LIKE '% Mormon' OR name = 'Mormon'
         OR name LIKE '% mormon %' OR name LIKE 'mormon %' OR name LIKE '% mormon')
     OR (name LIKE '%Stake Center%' OR name LIKE '%Stake Centre%')
     OR (denomination LIKE '%Latter%' OR denomination LIKE '%Mormon%' OR denomination LIKE '%LDS%'))
    AND name NOT LIKE '%Baptist%' AND name NOT LIKE '%Catholic%'
    AND name NOT LIKE '%Methodist%' AND name NOT LIKE '%Lutheran%'
    AND name NOT LIKE '%Presbyterian%' AND name NOT LIKE '%Anglican%'
    AND name NOT LIKE '%Pentecostal%' AND name NOT LIKE '%Evangelical%'
    AND name NOT LIKE '%Adventist%'
    AND name NOT LIKE '%Hindu%' AND name NOT LIKE '%Buddhist%'
    AND name NOT LIKE '%Sri %' AND name NOT LIKE '%Krishna%' AND name NOT LIKE '%Hanuman%'
    AND denomination NOT LIKE '%FLD%'
    AND name NOT LIKE '%FLDS%'
    AND name NOT LIKE '%Polygamy%'
    AND name NOT LIKE '%Work of Jesus Christ%'
    AND name NOT LIKE '%Yearning for Zion%'
    AND name NOT LIKE '%Community of Grace%'
"""

def detect_lds_type(name, has_gps, faith=None, denomination=None):
    """Detect LDS building type from name."""
    low = name.lower().strip()
    faith_low = (faith or '').lower()
    denom_low = (denomination or '').lower()
    is_lds_denom = 'latter' in denom_low or 'mormon' in denom_low or 'lds' in denom_low
    
    # ── Non-building / false-positive patterns (exclude or tag as 'other') ──
    # English classes, youth camps, programs, etc.
    if re.search(r'\bclass\b', low) and ('english' in low or 'free' in low):
        return 'other', None
    if 'youth camp' in low or 'youth ranch' in low:
        return 'other', None
    if 'welfare farm' in low or 'welfare department' in low:
        return 'employment_center', None
    
    # Non-building patterns (ministries to be collapsed)
    ward_match = re.search(r'\bward\b', low)
    branch_match = re.search(r'\bbranch\b', low)
    
    # HQ
    if 'church office building' in low or 'world headquarters' in low:
        return 'hq', None
    
    # Area Office
    if 'area office' in low or 'area presidency' in low or 'area director' in low:
        return 'area_office', None
    
    # Temple — only if faith is Christian-like OR denomination is LDS
    if re.search(r'\btemple\b', low):
        # Exclude non-LDS temples by name pattern
        if any(kw in low for kw in ['hindu', 'sri ', 'krishna', 'hanuman', 'sivan',
                                     'buddhist', 'shrine', 'mandir', 'gurdwara',
                                     'church of god', 'umc', 'cme', 'ame',
                                     'baptist', 'methodist', 'presbyterian',
                                     'lutheran', 'episcopal', 'anglican']):
            # Check if it's STILL an LDS temple (e.g., "Philadelphia Mormon Temple")
            if not any(lds_kw in low for lds_kw in ['mormon', 'lds', 'latter']):
                return 'meetinghouse', None
        if not is_lds_denom:
            # Check name for LDS keywords
            if not any(lds_kw in low for lds_kw in ['mormon', 'lds', 'latter']):
                # Check faith
                if faith_low and faith_low not in ('christian', '', 'other'):
                    return 'meetinghouse', None
        detail = None
        if 'salt lake temple' in low:
            detail = 'hq'
        return 'temple', detail
    
    # Mission Office
    if 'mission office' in low or 'mission president' in low:
        return 'mission_office', None
    
    # Institute of Religion (broad match for any LDS institute)
    if re.search(r'\binstitute\b', low):
        # Check it's LDS-related (name has LDS, Mormon, or Latter-day)
        if 'lds' in low or 'mormon' in low or 'latter' in low or is_lds_denom:
            return 'institute', None
    
    # Seminary
    if re.search(r'\bseminary\b', low):
        return 'seminary', None
    
    # Storehouse
    if 'storehouse' in low or "bishop's storehouse" in low:
        return 'storehouse', None
    
    # Employment Center (also catches welfare, self-reliance)
    if 'employment' in low or 'self-reliance' in low:
        return 'employment_center', None
    
    # Family History Center
    if 'family history' in low:
        return 'family_history_center', None
    
    # Stake Center (explicit) or Stake
    # Stake Center (explicit) or Stake
    if 'stake center' in low or re.search(r'\bstake\b', low):
        return 'stake_house', None
    
    # Deseret Industries
    if 'deseret' in low:
        return 'employment_center', None
    
    # Ward, Branch, Meetinghouse — these are meetinghouses
    if ward_match or branch_match or 'meetinghouse' in low or 'ward house' in low:
        return 'meetinghouse', None
    
    # Generic "Church of Jesus Christ of Latter-day Saints" — meetinghouse
    if 'church of jesus christ' in low and ('latter' in low or 'lds' in low):
        return 'meetinghouse', None
    
    # Generic LDS / Mormon
    if 'mormon' in low or 'lds' in low:
        if not has_gps:
            return 'other', None
        return 'meetinghouse', None
    
    return 'other', None


def extract_detail(name, lds_type):
    """Extract ministry info from name."""
    low = name.lower().strip()
    
    if lds_type == 'stake_house':
        # Extract stake name
        m = re.search(r'(.+?)\s+stake', name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None
    
    if lds_type == 'meetinghouse':
        # Extract ward/branch name
        ward_m = re.search(r'(.+?)\s+ward', name, re.IGNORECASE)
        branch_m = re.search(r'(.+?)\s+branch', name, re.IGNORECASE)
        if ward_m:
            return f"ward: {ward_m.group(1).strip()}"
        if branch_m:
            return f"branch: {branch_m.group(1).strip()}"
        return None
    
    if lds_type == 'temple':
        m = re.search(r'(.+?)\s+temple', name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None
    
    return None


print("=" * 60)
print("LDS Hierarchy Creator")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Step 1: Create table
print("\n[1/5] Creating lds_hierarchy table...")
c.execute("""
    CREATE TABLE IF NOT EXISTS lds_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES lds_hierarchy(id),
        church_id INTEGER,
        name TEXT NOT NULL,
        original_name TEXT,
        lds_type TEXT NOT NULL CHECK(lds_type IN (
            'hq', 'area_office', 'temple', 'mission_office',
            'stake_house', 'meetinghouse',
            'institute', 'seminary', 'storehouse',
            'employment_center', 'family_history_center',
            'other'
        )),
        lds_detail TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        parent_lds_type TEXT,
        relationship TEXT CHECK(relationship IN (
            'administered_by',
            'affiliated_with',
            'served_by'
        )),
        ministries TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        CONSTRAINT unique_lds_link UNIQUE(church_id, parent_id, relationship)
    )
""")
db.commit()
print("  Table created.")

# Check existing
existing = c.execute("SELECT COUNT(*) FROM lds_hierarchy").fetchone()[0]
if existing > 0:
    print(f"  lds_hierarchy already has {existing:,} rows — deleting and rebuilding...")
    if not dry_run:
        c.execute("DELETE FROM lds_hierarchy")
        db.commit()

# Step 2: Find HQ
print("\n[2/5] Finding HQ entry...")
hq = c.execute("""
    SELECT id, name, city, state, country, latitude, longitude
    FROM churches
    WHERE (name LIKE '%Church Office Building%' AND city = 'Salt Lake City')
       OR (name LIKE '%50 E North Temple%')
    LIMIT 1
""").fetchone()

if not hq:
    # Fallback: Salt Lake Temple
    hq = c.execute("""
        SELECT id, name, city, state, country, latitude, longitude
        FROM churches
        WHERE name LIKE '%Salt Lake Temple%'
        LIMIT 1
    """).fetchone()

if hq:
    print(f"  HQ: #{hq[0]} {hq[1][:50]} | {hq[2]}, {hq[3]}")
else:
    print("  WARNING: No HQ entry found!")

# Step 3: Gather LDS entries
print("\n[3/5] Gathering LDS entries...")
rows = c.execute(f"""
    SELECT id, name, city, state, country, latitude, longitude, source,
           COALESCE(faith, ''), COALESCE(denomination, '')
    FROM churches
    WHERE id IS NOT NULL AND {lds_where}
    ORDER BY name
""").fetchall()
print(f"  Found {len(rows):,} LDS entries with valid id")

# Step 4: Classify
print("\n[4/5] Classifying...")
type_counts = {}
building_rows = []  # Will become hierarchy rows
ministry_buckets = {}  # {meetinghouse_key: [ministry_dicts]}

for church_id, name, city, state, country, lat, lon, source, faith, denomination in rows:
    has_gps = lat is not None
    lds_type, type_detail = detect_lds_type(name, has_gps, faith, denomination)
    detail = extract_detail(name, lds_type) or type_detail
    
    type_counts[lds_type] = type_counts.get(lds_type, 0) + 1
    
    city_clean = city if city and city != 'None' else None
    state_clean = state if state and state != 'None' else None
    country_clean = country if country and country != 'None' else None
    
    building_rows.append({
        'church_id': church_id,
        'name': name,
        'lds_type': lds_type,
        'lds_detail': detail,
        'city': city_clean,
        'state': state_clean,
        'country': country_clean,
        'lat': lat,
        'lon': lon,
    })

for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:25s}: {cnt:>6,}")

# Step 5: Insert
print(f"\n[5/5] Inserting {len(building_rows):,} rows...")
if dry_run:
    print("  (skipped — dry run)")
else:
    # Insert HQ first if exists
    if hq:
        c.execute("""
            INSERT INTO lds_hierarchy (church_id, name, lds_type, lds_detail, city, state, country, lat, lon)
            VALUES (?, ?, 'hq', NULL, ?, ?, ?, ?, ?)
        """, (hq[0], hq[1], hq[2], hq[3], hq[4], hq[5], hq[6]))
    
    # Batch insert buildings
    inserted = 0
    for br in building_rows:
        c.execute("""
            INSERT INTO lds_hierarchy
                (church_id, name, lds_type, lds_detail, city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (br['church_id'], br['name'], br['lds_type'], br['lds_detail'],
              br['city'], br['state'], br['country'], br['lat'], br['lon']))
        inserted += 1
        if inserted % CHUNK == 0:
            db.commit()
            print(f"    Inserted {inserted:,}...", flush=True)
    
    db.commit()
    print(f"  ✓ Inserted {inserted:,} rows")
    
    # Create indexes
    print("\n  Creating indexes...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lds_type ON lds_hierarchy(lds_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lds_parent ON lds_hierarchy(parent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_lds_church ON lds_hierarchy(church_id)")
    db.commit()

    # Log provenance
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at,
                                     churches_updated, records_attempted, status)
        VALUES ('lds_hierarchy', 'create_lds_hierarchy.py', ?,
                ?, ?, 'completed')
    """, (now, inserted, len(rows)))
    db.commit()

# Summary
print(f"\n{'='*60}")
total = c.execute("SELECT COUNT(*) FROM lds_hierarchy").fetchone()[0]
print(f"Total lds_hierarchy rows: {total:,}")
for r in c.execute("SELECT lds_type, COUNT(*) FROM lds_hierarchy GROUP BY lds_type ORDER BY COUNT(*) DESC"):
    print(f"  {r[1]:>6,} | {r[0]}")

db.close()
print("\nDone.")

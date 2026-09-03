"""
Create the moravian_hierarchy table and populate it from churches data.

Moravian Church (Unitas Fratrum) organizational structure — an episcopal
denomination organized into provinces, each with its own HQ.

Building types:
  hq              World HQ (Herrnhut, Germany — not yet in DB)
  province_hq     Provincial headquarters (e.g., Bethlehem PA, Winston-Salem NC)
  congregation    Local Moravian church
  mission         Mission outpost
  school          School, academy, seminary, college
  office          Other administrative office building
  other           Unclassified

Province structure (for Northern Province / US):
  Province HQ (Bethlehem, PA)
    └── Congregations across the US
    └── Schools / Seminaries

Usage:
    python scripts/db_maintenance/create_moravian_hierarchy.py
    python scripts/db_maintenance/create_moravian_hierarchy.py --dry-run
"""
import sqlite3, re, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

# Province HQ candidates — these will be the top-level nodes
PROVINCE_HQ_IDS = {
    5040297: 'Northern Province',   # Central Moravian Church Office Building
    3546180: 'Northern Province',   # MORAVIAN CHURCH NORTHERN PROVINCE
    5040165: 'Northern Province',   # Moravian Church Center (Bethlehem)
    3628299: 'Interprovincial',     # INTERPROVINCIAL BOARD OF COMMUNICATION
    4994208: 'Southern Province',   # Christ Moravian Office (Winston-Salem)
}


def detect_moravian_type(name, faith):
    """Detect Moravian building type from name."""
    low = name.lower().strip()
    faith_low = (faith or '').lower()
    
    # Office / HQ / Center / Administration / Board / Province
    if re.search(r'\b(office|headquarters|administration|board)\b', low):
        return 'province_hq', None
    if re.search(r'\bprovince\b', low):
        return 'province_hq', None
    if re.search(r'\b(center|centre)\b', low) and ('moravian church' in low or 'moravian' in low):
        # "Moravian Church Center" — could be admin office
        if 'church' not in low or ('center' in low and 'church center' in low):
            return 'province_hq', None
    
    # School / Academy / College / Seminary
    if re.search(r'\b(school|academy|college|seminary|university)\b', low):
        return 'school', None
    
    # Mission
    if re.search(r'\bmission\b', low):
        return 'mission', None
    
    # Cemetery / Memorial Garden / Burial
    if re.search(r'\b(cemetery|burial|memorial garden)\b', low):
        return 'other', None
    
    # Congregation / Church / Chapel / Fellowship
    if re.search(r'\b(church|congregation|chapel|fellowship|ministry)\b', low):
        return 'congregation', None
    
    # Generic Moravian name
    if 'moravian' in low or 'moravska' in low or 'herrnhut' in low:
        # Check faith — if Other, could be an office or unclassified
        if faith_low in ('other', ''):
            return 'other', None
        return 'congregation', None
    
    return 'other', None


def extract_moravian_detail(name, moravian_type):
    """Extract additional detail from name."""
    low = name.lower().strip()
    
    if moravian_type == 'congregation':
        # Extract congregation name before "Moravian Church"
        m = re.search(r'(.+?)\s+moravian\s+(church|congregation|chapel)', name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None
    
    if moravian_type == 'school':
        m = re.search(r'(.+?)\s+(school|academy|seminary|college)', name, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None
    
    return None


print("=" * 60)
print("Moravian Hierarchy Creator")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Step 0: Fix faith on Moravian office buildings
print("\n[0/6] Fixing faith on Moravian office buildings...")
fix_ids = list(PROVINCE_HQ_IDS.keys())
for fid in fix_ids:
    cur_faith = c.execute("SELECT faith FROM churches WHERE id = ?", (fid,)).fetchone()
    if cur_faith and cur_faith[0] in ('Other', None, ''):
        if not dry_run:
            c.execute("UPDATE churches SET faith = 'Christian' WHERE id = ?", (fid,))
            print(f"  #{fid}: faith Other → Christian")
        else:
            print(f"  #{fid}: would fix from {cur_faith[0]} → Christian")
db.commit()
print("  Faith fixes applied.")

# Step 1: Create table
print("\n[1/6] Creating moravian_hierarchy table...")
c.execute("""
    CREATE TABLE IF NOT EXISTS moravian_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES moravian_hierarchy(id),
        church_id INTEGER,
        name TEXT NOT NULL,
        original_name TEXT,
        moravian_type TEXT NOT NULL CHECK(moravian_type IN (
            'hq', 'province_hq', 'congregation', 'mission', 'school', 'office', 'other'
        )),
        moravian_detail TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        parent_moravian_type TEXT,
        relationship TEXT CHECK(relationship IN (
            'administered_by',
            'affiliated_with'
        )),
        ministries TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        CONSTRAINT unique_moravian_link UNIQUE(church_id, parent_id, relationship)
    )
""")
db.commit()
print("  Table created.")

# Check existing
existing = c.execute("SELECT COUNT(*) FROM moravian_hierarchy").fetchone()[0]
if existing > 0:
    print(f"  moravian_hierarchy already has {existing:,} rows — deleting and rebuilding...")
    if not dry_run:
        c.execute("DELETE FROM moravian_hierarchy")
        db.commit()

# Step 2: Gather Moravian entries
print("\n[2/6] Gathering Moravian entries...")
rows = c.execute("""
    SELECT id, name, city, state, country, latitude, longitude, source,
           COALESCE(faith, '')
    FROM churches
    WHERE id IS NOT NULL
      AND (name LIKE '%Moravian%'
           OR name LIKE '%Moravska%'
           OR name LIKE '%Herrnhut%'
           OR denomination LIKE '%Moravian%')
      AND faith != 'Judaism'  -- exclude misclassified
    ORDER BY name
""").fetchall()
print(f"  Found {len(rows):,} Moravian entries")

# Step 3: Separate HQ candidates from regular entries
hq_rows = []
regular_rows = []
for r in rows:
    if r[0] in PROVINCE_HQ_IDS:
        hq_rows.append(r)
    else:
        regular_rows.append(r)

print(f"  Province HQ candidates: {len(hq_rows):,}")
print(f"  Regular entries: {len(regular_rows):,}")

# Step 4: Classify
print("\n[4/6] Classifying...")
type_counts = {}
building_rows = []

for church_id, name, city, state, country, lat, lon, source, faith in regular_rows:
    moravian_type, type_detail = detect_moravian_type(name, faith)
    detail = extract_moravian_detail(name, moravian_type) or type_detail
    
    type_counts[moravian_type] = type_counts.get(moravian_type, 0) + 1
    
    city_clean = city if city and city != 'None' else None
    state_clean = state if state and state != 'None' else None
    country_clean = country if country and country != 'None' else None
    
    building_rows.append({
        'church_id': church_id,
        'name': name,
        'moravian_type': moravian_type,
        'moravian_detail': detail,
        'city': city_clean,
        'state': state_clean,
        'country': country_clean,
        'lat': lat,
        'lon': lon,
    })

for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:20s}: {cnt:>6,}")

# Step 5: Insert
total_rows = len(hq_rows) + len(building_rows)
print(f"\n[5/6] Inserting {total_rows:,} rows...")
if dry_run:
    print("  (skipped — dry run)")
else:
    inserted = 0
    
    # Insert province HQ entries first
    hq_hids = {}  # church_id → hierarchy id
    for r in hq_rows:
        church_id, name, city, state, country, lat, lon, source, faith = r
        city_clean = city if city and city != 'None' else None
        state_clean = state if state and state != 'None' else None
        country_clean = country if country and country != 'None' else None
        
        detail = PROVINCE_HQ_IDS.get(church_id, '')
        c.execute("""
            INSERT INTO moravian_hierarchy
                (church_id, name, moravian_type, moravian_detail, city, state, country, lat, lon)
            VALUES (?, ?, 'province_hq', ?, ?, ?, ?, ?, ?)
        """, (church_id, name, detail, city_clean, state_clean, country_clean, lat, lon))
        hq_hids[church_id] = c.lastrowid
        inserted += 1
    
    # Batch insert regular entries
    for br in building_rows:
        c.execute("""
            INSERT INTO moravian_hierarchy
                (church_id, name, moravian_type, moravian_detail, city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (br['church_id'], br['name'], br['moravian_type'], br['moravian_detail'],
              br['city'], br['state'], br['country'], br['lat'], br['lon']))
        inserted += 1
        if inserted % CHUNK == 0:
            db.commit()
            print(f"    Inserted {inserted:,}/{total_rows:,}...", flush=True)
    
    db.commit()
    print(f"  ✓ Inserted {inserted:,} rows")
    
    # Step 6: Link congregations to province HQ (by country proximity)
    print("\n[6/6] Linking congregations to province HQ...")
    
    # Find the Northern Province HQ hierarchy IDs (Bethlehem, PA)
    northern_hids = [hid for cid, hid in hq_hids.items()
                     if PROVINCE_HQ_IDS.get(cid) == 'Northern Province']
    
    linked = 0
    if northern_hids:
        # US congregations → Northern Province HQ
        main_northern_hid = northern_hids[0]
        
        for br in building_rows:
            if br['country'] == 'US' and br['moravian_type'] in ('congregation', 'mission', 'school', 'other'):
                child_hid = c.execute("""
                    SELECT id FROM moravian_hierarchy
                    WHERE church_id = ? AND moravian_type = ?
                """, (br['church_id'], br['moravian_type'])).fetchone()
                if child_hid:
                    c.execute("""
                        UPDATE moravian_hierarchy
                        SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'administered_by'
                        WHERE id = ?
                    """, (main_northern_hid, child_hid[0]))
                    linked += 1
                    if linked % CHUNK == 0:
                        db.commit()
                        print(f"    Linked {linked:,}...", flush=True)
    
    db.commit()
    print(f"  ✓ {linked:,} US entries linked to Northern Province HQ")
    
    # Create indexes
    print("\n  Creating indexes...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_moravian_type ON moravian_hierarchy(moravian_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_moravian_parent ON moravian_hierarchy(parent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_moravian_church ON moravian_hierarchy(church_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_moravian_country ON moravian_hierarchy(country)")
    db.commit()
    
    # Log provenance
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at,
                                     churches_updated, records_attempted, status)
        VALUES ('moravian_hierarchy', 'create_moravian_hierarchy.py', ?,
                ?, ?, 'completed')
    """, (now, inserted, len(rows)))
    db.commit()

# Summary
print(f"\n{'='*60}")
total = c.execute("SELECT COUNT(*) FROM moravian_hierarchy").fetchone()[0]
print(f"Total moravian_hierarchy rows: {total:,}")
for r in c.execute("SELECT moravian_type, COUNT(*) FROM moravian_hierarchy GROUP BY moravian_type ORDER BY COUNT(*) DESC"):
    print(f"  {r[1]:>6,} | {r[0]}")
linked_count = c.execute("SELECT COUNT(*) FROM moravian_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f"  {linked_count:>6,} | linked to province HQ")

db.close()
print("\nDone.")

"""
Create the chabad_hierarchy table and populate it from churches data.

Chabad-Lubavitch is a Hasidic Jewish movement with a clear emissary-based
organizational structure. Chabad centers worldwide are shliach (emissary)
outposts of the central Lubavitch movement.

Building types:
  hq              World Headquarters (770 Eastern Parkway, Brooklyn)
  regional_office Regional administrative office
  chabad_house    Standard Chabad-Lubavitch center
  campus_chabad   University/college Chabad
  other           Unclassified

Hierarchy:
  HQ → Chabad Houses / Campus Chabad / Regional Offices
  (mostly flat — each center is a direct emissary of the Rebbe)

Usage:
    python scripts/db_maintenance/create_chabad_hierarchy.py
    python scripts/db_maintenance/create_chabad_hierarchy.py --dry-run
"""
import sqlite3, re, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

CHABAD_HQ_ID = 270192  # CHABAD LUBAVITCH WORLD HEADQUARTERS

def detect_chabad_type(name):
    """Detect Chabad building type from name."""
    low = name.lower().strip()
    
    # World HQ
    if 'world headquarters' in low and 'chabad' in low:
        return 'hq', None
    
    # Regional office / central organization
    if re.search(r'\b(regional|organization|executive|national|international)\b', low):
        detail = None
        for kw in ['regional', 'central', 'national', 'international', 'executive']:
            m = re.search(r'\b' + kw + r'\b', low, re.IGNORECASE)
            if m:
                detail = kw.title()
                break
        return 'regional_office', detail
    
    # Campus / university / college
    if re.search(r'\b(campus|university|college|student)\b', low):
        return 'campus_chabad', None
    
    # Chabad House / Center / Jewish Center (explicit)
    if re.search(r'\bchabad\s*(house|center|centre|jewish center|jewish centre)\b', low):
        return 'chabad_house', None
    
    # Chabad Lubavitch of [Place] — standard center naming
    if re.search(r'chabad\s+lubavitch\s+of\b', low):
        return 'chabad_house', None
    
    # Chabad of [Place]
    if re.search(r'\bchabad\s+of\b', low):
        return 'chabad_house', None
    
    # Generic Chabad name — likely a center
    if 'chabad' in low:
        return 'chabad_house', None
    
    return 'other', None


print("=" * 60)
print("Chabad Hierarchy Creator")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Step 1: Create table
print("\n[1/5] Creating chabad_hierarchy table...")
c.execute("""
    CREATE TABLE IF NOT EXISTS chabad_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES chabad_hierarchy(id),
        church_id INTEGER,
        name TEXT NOT NULL,
        original_name TEXT,
        chabad_type TEXT NOT NULL CHECK(chabad_type IN (
            'hq', 'regional_office', 'chabad_house', 'campus_chabad', 'other'
        )),
        chabad_detail TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        lat REAL,
        lon REAL,
        parent_chabad_type TEXT,
        relationship TEXT CHECK(relationship IN (
            'affiliated_with'
        )),
        ministries TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        CONSTRAINT unique_chabad_link UNIQUE(church_id, parent_id, relationship)
    )
""")
db.commit()
print("  Table created.")

# Check existing
existing = c.execute("SELECT COUNT(*) FROM chabad_hierarchy").fetchone()[0]
if existing > 0:
    print(f"  chabad_hierarchy already has {existing:,} rows — deleting and rebuilding...")
    if not dry_run:
        c.execute("DELETE FROM chabad_hierarchy")
        db.commit()

# Step 2: Verify HQ entry
print("\n[2/5] Verifying HQ entry...")
hq = c.execute("""
    SELECT id, name, city, state, country, latitude, longitude
    FROM churches WHERE id = ?
""", (CHABAD_HQ_ID,)).fetchone()

if hq:
    print(f"  HQ: #{hq[0]} {hq[1]} | {hq[2]}, {hq[3]} {hq[4]}")
else:
    print(f"  WARNING: HQ entry #{CHABAD_HQ_ID} not found!")

# Step 3: Gather Chabad entries
print("\n[3/5] Gathering Chabad entries...")
rows = c.execute("""
    SELECT id, name, city, state, country, latitude, longitude, source
    FROM churches
    WHERE id IS NOT NULL
      AND name LIKE '%Chabad%'
      AND id != ?
    ORDER BY name
""", (CHABAD_HQ_ID,)).fetchall()
print(f"  Found {len(rows):,} Chabad entries (excluding HQ)")

# Step 4: Classify
print("\n[4/5] Classifying...")
type_counts = {}
building_rows = []

for church_id, name, city, state, country, lat, lon, source in rows:
    chabad_type, type_detail = detect_chabad_type(name)
    
    type_counts[chabad_type] = type_counts.get(chabad_type, 0) + 1
    
    city_clean = city if city and city != 'None' else None
    state_clean = state if state and state != 'None' else None
    country_clean = country if country and country != 'None' else None
    
    building_rows.append({
        'church_id': church_id,
        'name': name,
        'chabad_type': chabad_type,
        'chabad_detail': type_detail,
        'city': city_clean,
        'state': state_clean,
        'country': country_clean,
        'lat': lat,
        'lon': lon,
    })

for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:20s}: {cnt:>6,}")

# Step 5: Insert
print(f"\n[5/5] Inserting {len(building_rows) + 1:,} rows (incl. HQ)...")
if dry_run:
    print("  (skipped — dry run)")
else:
    # Insert HQ first
    c.execute("""
        INSERT INTO chabad_hierarchy (church_id, name, chabad_type, city, state, country, lat, lon)
        VALUES (?, ?, 'hq', ?, ?, ?, ?, ?)
    """, (hq[0], hq[1], hq[2], hq[3], hq[4], hq[5], hq[6]))
    
    # Batch insert buildings
    inserted = 0
    for br in building_rows:
        c.execute("""
            INSERT INTO chabad_hierarchy
                (church_id, name, chabad_type, chabad_detail, city, state, country, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (br['church_id'], br['name'], br['chabad_type'], br['chabad_detail'],
              br['city'], br['state'], br['country'], br['lat'], br['lon']))
        inserted += 1
        if inserted % CHUNK == 0:
            db.commit()
            print(f"    Inserted {inserted:,}...", flush=True)
    
    db.commit()
    print(f"  ✓ Inserted {inserted + 1:,} rows")
    
    # Now link all entries to HQ
    print("\n  Linking entries to HQ...")
    hq_hid = c.execute("SELECT id FROM chabad_hierarchy WHERE church_id = ?", (CHABAD_HQ_ID,)).fetchone()[0]
    
    linked = 0
    for br in building_rows:
        # Find the hierarchy row for this church
        child_hid = c.execute("""
            SELECT id FROM chabad_hierarchy
            WHERE church_id = ? AND chabad_type = ?
        """, (br['church_id'], br['chabad_type'])).fetchone()
        if child_hid:
            c.execute("""
                UPDATE chabad_hierarchy
                SET parent_id = ?, parent_chabad_type = 'hq', relationship = 'affiliated_with'
                WHERE id = ?
            """, (hq_hid, child_hid[0]))
            linked += 1
            if linked % CHUNK == 0:
                db.commit()
                print(f"    Linked {linked:,}...", flush=True)
    
    db.commit()
    print(f"  ✓ {linked:,} entries linked to HQ")
    
    # Create indexes
    print("\n  Creating indexes...")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chabad_type ON chabad_hierarchy(chabad_type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chabad_parent ON chabad_hierarchy(parent_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chabad_church ON chabad_hierarchy(church_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chabad_country ON chabad_hierarchy(country)")
    db.commit()
    
    # Log provenance
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at,
                                     churches_updated, records_attempted, status)
        VALUES ('chabad_hierarchy', 'create_chabad_hierarchy.py', ?,
                ?, ?, 'completed')
    """, (now, inserted + 1, len(rows) + 1))
    db.commit()

# Summary
print(f"\n{'='*60}")
total = c.execute("SELECT COUNT(*) FROM chabad_hierarchy").fetchone()[0]
print(f"Total chabad_hierarchy rows: {total:,}")
for r in c.execute("SELECT chabad_type, COUNT(*) FROM chabad_hierarchy GROUP BY chabad_type ORDER BY COUNT(*) DESC"):
    print(f"  {r[1]:>6,} | {r[0]}")
print(f"  {c.execute('SELECT COUNT(*) FROM chabad_hierarchy WHERE parent_id IS NOT NULL').fetchone()[0]:>6,} | linked to HQ")

db.close()
print("\nDone.")

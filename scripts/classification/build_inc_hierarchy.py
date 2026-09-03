"""
Build Iglesia Ni Cristo hierarchy: Central Office → Districts → Locales.

INC structure:
  Central Office (Quezon City) 
    → Ecclesiastical Districts (~150 worldwide, ~100 in PH)
      → Locales (congregations, "Lokal ng [Place]")

Since we don't have explicit district assignments, we use geographic clustering:
- Group locales by province/state
- Each province = a district hub
- Link to Central Office
"""

import sqlite3
import numpy as np
from math import radians, cos, sin, asin, sqrt

DB = "E:/grid/churches.db"

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return R * 2 * asin(sqrt(a))

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

print("=" * 60)
print("IGLESIA NI CRISTO — HIERARCHY BUILD")
print("=" * 60)

# ── Step 1: Find all INC locales ─────────────────────────────────────
print("\n[1/4] Loading INC locales...")
cursor = db.execute("""
    SELECT rowid, name, name_english, city, state, latitude, longitude, landmark_type
    FROM churches
    WHERE country = 'PH'
      AND tradition = 'Iglesia Ni Cristo'
      AND landmark_type != 'data_artifact'
      AND latitude IS NOT NULL
""")
locales = [dict(r) for r in cursor.fetchall()]
print(f"  {len(locales):,} INC locales with GPS")

# ── Step 2: Find / create Central Office ──────────────────────────────
print("\n[2/4] Identifying Central Office...")

# Look for HQ in Quezon City
hq_keywords = ['Central', 'Templo', 'Temple', 'Main', 'Headquarter', 'Central Office']
hq = None
for r in locales:
    name = r['name'].lower()
    if 'central' in name and ('quezon' in r['city'].lower() or r['state'] == 'NCR'):
        hq = r
        break

if not hq:
    # Look for INC Central Temple in Quezon City
    for r in locales:
        if 'templo' in r['name'].lower() or 'temple' in r['name'].lower():
            if r['state'] == 'NCR':
                hq = r
                break

if not hq:
    # Fallback: any INC in Quezon City
    for r in locales:
        if 'quezon' in r['city'].lower() or r['state'] == 'NCR':
            hq = r
            break

if not hq:
    hq = locales[0]

print(f"  HQ: {hq['name']} ({hq['city']}, {hq['state']})")

# ── Step 3: Create hierarchy table ────────────────────────────────────
print("\n[3/4] Creating inc_hierarchy table...")

db.execute("DROP TABLE IF EXISTS inc_hierarchy")
db.execute("""
    CREATE TABLE inc_hierarchy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES inc_hierarchy(id),
        church_id INTEGER,
        name TEXT NOT NULL,
        inc_type TEXT NOT NULL CHECK(inc_type IN ('central_office','district','locale','other')),
        city TEXT,
        state TEXT,
        lat REAL,
        lon REAL,
        relationship TEXT CHECK(relationship IN ('headquartered_at','administered_by','belongs_to')),
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")
db.commit()

# Insert HQ
db.execute("""
    INSERT INTO inc_hierarchy (church_id, name, inc_type, city, state, lat, lon, relationship, notes)
    VALUES (?, ?, 'central_office', ?, ?, ?, ?, NULL, 'Iglesia Ni Cristo Central Office, Quezon City')
""", (hq['rowid'], hq['name'], hq['city'], hq['state'], hq['latitude'], hq['longitude']))
hq_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

# ── Step 4: Group by state → create district hubs ─────────────────────
print("\n[4/4] Building district hierarchy...")

state_groups = {}
for r in locales:
    s = r['state']
    if s not in state_groups:
        state_groups[s] = []
    state_groups[s].append(r)

district_count = 0
locale_count = 0

for state, churches_in_state in sorted(state_groups.items()):
    if state == hq['state'] and len(churches_in_state) <= 3:
        # Small state — HQ serves as district
        for r in churches_in_state:
            if r['rowid'] == hq['rowid']:
                continue
            db.execute("""
                INSERT INTO inc_hierarchy (parent_id, church_id, name, inc_type, city, state, lat, lon, relationship, notes)
                VALUES (?, ?, ?, 'locale', ?, ?, ?, ?, 'belongs_to', ?)
            """, (hq_id, r['rowid'], r['name'], r['city'], r['state'], r['latitude'], r['longitude'], f"Locale in {state}"))
            locale_count += 1
        continue
    
    # Find district hub: prefer entries with "District Office" in name
    district_hub = None
    for r in churches_in_state:
        if 'district office' in r['name'].lower() or 'district' in r['name'].lower():
            district_hub = r
            break
    
    if not district_hub:
        # Use the most central church as district hub
        if len(churches_in_state) >= 2:
            lats = [r['latitude'] for r in churches_in_state if r['latitude']]
            lons = [r['longitude'] for r in churches_in_state if r['longitude']]
            if lats and lons:
                center_lat, center_lon = np.mean(lats), np.mean(lons)
                district_hub = min(churches_in_state, 
                    key=lambda r: haversine(r['latitude'], r['longitude'], center_lat, center_lon) 
                    if r['latitude'] else float('inf'))
            else:
                district_hub = churches_in_state[0]
        else:
            district_hub = churches_in_state[0]
    
    # Insert district hub
    db.execute("""
        INSERT INTO inc_hierarchy (parent_id, church_id, name, inc_type, city, state, lat, lon, relationship, notes)
        VALUES (?, ?, ?, 'district', ?, ?, ?, ?, 'administered_by', ?)
    """, (hq_id, district_hub['rowid'], district_hub['name'], district_hub['city'], 
          district_hub['state'], district_hub['latitude'], district_hub['longitude'],
          f"District hub for {state}"))
    
    district_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    district_count += 1
    
    # Link remaining locales
    for r in churches_in_state:
        if r['rowid'] == district_hub['rowid'] or (district_hub['state'] == hq['state'] and r['rowid'] == hq['rowid']):
            continue
        db.execute("""
            INSERT INTO inc_hierarchy (parent_id, church_id, name, inc_type, city, state, lat, lon, relationship, notes)
            VALUES (?, ?, ?, 'locale', ?, ?, ?, ?, 'belongs_to', ?)
        """, (district_id, r['rowid'], r['name'], r['city'], r['state'], r['latitude'], r['longitude'],
              f"Locale in {state} district"))
        locale_count += 1

db.commit()

# ── Summary ──────────────────────────────────────────────────────────
print(f"\n  Hierarchy built:")
cursor = db.execute("SELECT inc_type, COUNT(*) as cnt FROM inc_hierarchy GROUP BY inc_type")
for r in cursor.fetchall():
    print(f"    {r['inc_type']:20s}: {r['cnt']:>5,}")

cursor = db.execute("SELECT relationship, COUNT(*) FROM inc_hierarchy WHERE relationship IS NOT NULL GROUP BY relationship")
for r in cursor.fetchall():
    print(f"    {r[0]:20s}: {r[1]:>5,}")

total = db.execute("SELECT COUNT(*) FROM inc_hierarchy").fetchone()[0]
print(f"\n    Total: {total:,} entries")
print(f"    1 Central Office → {district_count} Districts → {locale_count} Locales")

# ── Top districts ────────────────────────────────────────────────────
print(f"\n  Top districts by locale count:")
cursor = db.execute("""
    SELECT h.state, h.city, COUNT(*) as cnt
    FROM inc_hierarchy child
    JOIN inc_hierarchy h ON child.parent_id = h.id
    WHERE h.inc_type = 'district'
    GROUP BY h.state, h.city
    ORDER BY cnt DESC LIMIT 10
""")
for r in cursor.fetchall():
    print(f"    {r['state']:10s} {r['city']:20s} → {r['cnt']:>4,} locales")

db.close()
print("\n✅ Done. inc_hierarchy built.")

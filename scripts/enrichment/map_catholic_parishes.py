"""
Map all US Catholic parishes to their correct diocese using the county→diocese map file.

Uses: data/diocese_mapper/counties_by_diocese.csv — US county→Catholic diocese mapping (3,146 counties, 176 dioceses)

Phase 1: Match by county_fips_5 (direct lookup)
Phase 2: Spatial join using county polygon geometry (for churches without county_fips_5)

For each matched parish, inserts a row into catholic_hierarchy with:
  - parent_id → hierarchy id of the diocese
  - relationship = 'belongs_to_diocese'
  - diocese, archdiocese, province columns filled
"""
import sqlite3, csv, sys, os, re
from datetime import datetime, timezone
from shapely import wkt
from shapely.geometry import Point
from shapely.strtree import STRtree

DB = 'churches.db'
CSV_PATH = 'data/diocese_mapper/counties_by_diocese.csv'
STATE_FIPS_PATH = 'data/diocese_mapper/state_fips_codes.csv'
DRY_RUN = '--dry-run' in sys.argv
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
SOURCE = 'map_catholic_parishes'
CHUNK_SIZE = 500

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# ================================================================
# 0. Load state FIPS mapping
# ================================================================
state_fips = {}   # state_abbr -> 2-digit FIPS string
state_name_to_abbr = {}  # full state name -> abbreviation

with open(STATE_FIPS_PATH, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        abbr = row['State_Code'].strip()
        fips_num = int(row['FIPS'].strip())
        fips_str = str(fips_num).zfill(2)
        state_fips[abbr] = fips_str
        state_fips[abbr.lower()] = fips_str
        # Also index by full state name
        name = row['State_Name'].strip()
        state_name_to_abbr[name.lower()] = abbr
        state_name_to_abbr[name] = abbr

# Also add DC
state_fips['DC'] = '11'
state_fips['dc'] = '11'
print(f"  Loaded {len(state_fips)//2} state FIPS codes")

def normalize_fips(raw_fips, state_abbr=None):
    """
    Normalize a potentially messy county_fips_5 value to a proper 5-digit FIPS.
    Returns None if it can't be normalized.
    """
    if not raw_fips or not raw_fips.strip():
        return None
    
    raw = raw_fips.strip()
    
    # If it looks like a full state name, try to convert
    if len(raw) > 5 and raw.isalpha():
        raw_lower = raw.lower()
        if raw_lower in state_name_to_abbr:
            state_abbr = state_name_to_abbr[raw_lower]
            # Can't determine county from state name alone, return None
            return None
    
    # If it's already 5 digits and looks valid
    if len(raw) == 5 and raw.isdigit():
        # Check if first 2 chars are "00" — probably missing state prefix
        if raw.startswith('00') and state_abbr:
            state_f = state_fips.get(state_abbr.upper())
            if state_f:
                county_part = raw[2:].zfill(3)
                return state_f + county_part
        return raw  # Pass through as-is, may or may not be in CSV
    
    # If it's 1-3 digits, it's a county-only FIPS without state prefix
    if raw.isdigit() and len(raw) <= 3 and state_abbr:
        state_f = state_fips.get(state_abbr.upper())
        if state_f:
            county_part = raw.zfill(3)
            return state_f + county_part
    
    # If it's 4 digits with leading zeros (rare but possible)
    if raw.isdigit() and len(raw) == 4 and state_abbr:
        state_f = state_fips.get(state_abbr.upper())
        if state_f:
            return state_f + raw[-3:]
    
    return None

# ================================================================
# 1. Load county → diocese mapping from CSV
# ================================================================
print("=" * 70)
print("STEP 1: Load county→diocese mapping from CSV")
print("=" * 70)

# Build: FIPS_code → {diocese_name, province_name, geometry_wkt}
county_map = {}      # FIPS -> {diocese, province, archdiocese, geometry}
fips_to_diocese = {} # FIPS -> diocese_name (simplified lookup)

with open(CSV_PATH, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Use GEOID for full 5-digit county FIPS (e.g., "36039")
        fips = row['GEOID'].strip().zfill(5)
        diocese_name = row['Diocese'].strip()
        province_name = row['Province'].strip() if row['Province'] else ''
        diocese_detail = row.get('Diocese_Detail', '').strip()
        geom_wkt = row['geometry'].strip()
        
        county_map[fips] = {
            'diocese': diocese_name,
            'province': province_name,
            'diocese_detail': diocese_detail,
            'geometry': geom_wkt
        }
        fips_to_diocese[fips] = diocese_name

print(f"  Loaded {len(county_map):,} county→diocese mappings")
print(f"  Unique dioceses in CSV: {len(set(fips_to_diocese.values()))}")

# ================================================================
# 2. Build CSV diocese name → hierarchy ID mapping
# ================================================================
print("\n" + "=" * 70)
print("STEP 2: Build CSV→hierarchy diocese mapping")
print("=" * 70)

# Get all US diocese/archdiocese entries from hierarchy
c.execute("""
    SELECT id, name, cath_detail, cath_type, church_id, province, archdiocese
    FROM catholic_hierarchy 
    WHERE country = 'US' AND cath_type IN ('diocese', 'archdiocese')
    ORDER BY name
""")
hierarchy_dioceses = c.fetchall()
print(f"  US diocese/archdiocese entries in hierarchy: {len(hierarchy_dioceses)}")

# Build lookup: normalized detail name -> hierarchy entry
def normalize_for_match(name):
    """Normalize diocese name for matching."""
    if not name:
        return ''
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    # Normalize "St." -> "Saint"
    name = re.sub(r'\bSt\.?\b', 'Saint', name)
    return name.lower()

detail_to_hierarchy = {}
for h_id, h_name, h_detail, h_type, h_church_id, h_prov, h_arch in hierarchy_dioceses:
    if h_detail:
        key = normalize_for_match(h_detail)
        detail_to_hierarchy[key] = {
            'id': h_id,
            'name': h_name,
            'type': h_type,
            'province': h_prov,
            'archdiocese': h_arch
        }
    # Also index by h_name without prefix
    if h_name:
        # Extract city name from "Diocese of X" or "Archdiocese of X"
        for prefix in ['Diocese of ', 'Archdiocese of ']:
            if h_name.startswith(prefix):
                city_part = h_name[len(prefix):]
                key = normalize_for_match(city_part)
                if key not in detail_to_hierarchy:
                    detail_to_hierarchy[key] = {
                        'id': h_id,
                        'name': h_name,
                        'type': h_type,
                        'province': h_prov,
                        'archdiocese': h_arch
                    }

print(f"  Hierarchy index entries: {len(detail_to_hierarchy)}")

# Manual overrides for CSV names that don't match hierarchy format
MANUAL_MAP = {
    'St. Louis': 'Saint Louis',
    'St. Thomas': 'Saint Thomas',
    'St. Augustine': 'Saint Augustine',
    'St. Cloud': 'Saint Cloud',
    'St. Paul and Minneapolis': 'Saint Paul and Minneapolis',
    'St. Petersburg': 'Saint Petersburg',
    'Bismark': 'Bismarck',
    # Hierarchy uses "Birmingham in Alabama" as detail, but we match on base name
    'Birmingham': 'Birmingham in Alabama',
    # Hierarchy uses "Kansas City-Saint Joseph" with "Saint" not "St."
    'Kansas City-St. Joseph': 'Kansas City-Saint Joseph',
}

# Now map each CSV diocese to a hierarchy entry
csv_to_hierarchy = {}  # CSV diocese name -> hierarchy info
unmatched_csv = []

csv_diocese_names = set(fips_to_diocese.values())
for csv_name in sorted(csv_diocese_names):
    # Check manual override first
    if csv_name in MANUAL_MAP:
        mapped_name = MANUAL_MAP[csv_name]
        mapped_key = normalize_for_match(mapped_name)
        if mapped_key in detail_to_hierarchy:
            csv_to_hierarchy[csv_name] = detail_to_hierarchy[mapped_key]
            continue
    
    key = normalize_for_match(csv_name)
    
    if key in detail_to_hierarchy:
        csv_to_hierarchy[csv_name] = detail_to_hierarchy[key]
    else:
        # Try with "Saint" <-> "St." variations
        alt_key_variants = [
            key.replace('saint', 'st.'),
            key.replace('saint', 'st '),
            key.replace('st.', 'saint'),
            key.replace('st ', 'saint'),
        ]
        found = False
        for alt_key in alt_key_variants:
            if alt_key in detail_to_hierarchy:
                csv_to_hierarchy[csv_name] = detail_to_hierarchy[alt_key]
                found = True
                break
        
        if not found:
            # Try more aggressive matching
            matched = False
            for h_key, h_info in detail_to_hierarchy.items():
                # Check if key is a substring of h_key or vice versa
                if key in h_key or h_key in key:
                    csv_to_hierarchy[csv_name] = h_info
                    matched = True
                    break
            if not matched:
                unmatched_csv.append(csv_name)

print(f"  Matched {len(csv_to_hierarchy)}/{len(csv_diocese_names)} CSV dioceses to hierarchy")
if unmatched_csv:
    print(f"  UNMATCHED ({len(unmatched_csv)}): {unmatched_csv}")    
    # Attempt to create missing diocese entries in the hierarchy
    print(f"\n  Creating missing diocese entries...")
    
    # Pre-load province info from CSV
    csv_province_map = {}
    with open(CSV_PATH, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = row['Diocese'].strip()
            p = row.get('Province', '').strip()
            if d not in csv_province_map:
                csv_province_map[d] = p
    
    still_unmatched = []
    for csv_name in unmatched_csv:
        province_name = csv_province_map.get(csv_name, '')
        
        if not province_name:
            print(f"    Can't create '{csv_name}': no province info in CSV")
            still_unmatched.append(csv_name)
            continue
        
        # Find the archdiocese for this province in the hierarchy
        prov_key = normalize_for_match(province_name)
        arch_id = None
        arch_name = None
        for h_key, h_info in detail_to_hierarchy.items():
            if h_info['type'] == 'archdiocese' and (prov_key in h_key or h_key in prov_key):
                arch_id = h_info['id']
                arch_name = h_info['name']
                break
        
        if not arch_id:
            # Try SQL lookup
            c.execute("""
                SELECT id, name FROM catholic_hierarchy 
                WHERE country='US' AND cath_type='archdiocese' 
                AND (cath_detail LIKE ? OR name LIKE ?)
            """, (f'%{province_name}%', f'%{province_name}%'))
            arch_row = c.fetchone()
            if arch_row:
                arch_id = arch_row[0]
                arch_name = arch_row[1]
        
        if not arch_id:
            print(f"    Can't create '{csv_name}': archdiocese for province '{province_name}' not found")
            still_unmatched.append(csv_name)
            continue
        
        # Determine the canonical diocese name
        if csv_name == 'Birmingham':
            diocese_full_name = 'Diocese of Birmingham in Alabama'
            diocese_detail = 'Birmingham in Alabama'
        else:
            diocese_full_name = f'Diocese of {csv_name}'
            diocese_detail = csv_name
        
        # Create the diocese entry
        if not DRY_RUN:
            cur_max = c.execute("SELECT MAX(id) FROM catholic_hierarchy").fetchone()[0]
            new_id = (cur_max or 0) + 1
            
            c.execute("""
                INSERT INTO catholic_hierarchy 
                (id, parent_id, name, cath_type, cath_detail, diocese, archdiocese, 
                 province, country, parent_cath_type, relationship)
                VALUES (?, ?, ?, 'diocese', ?, ?, ?, ?, 'US', 'archdiocese', 'suffragan_of')
            """, (new_id, arch_id, diocese_full_name, diocese_detail, 
                  diocese_full_name, arch_name, province_name))
            db.commit()
            
            # Add to our mapping
            entry_key = normalize_for_match(diocese_detail)
            detail_to_hierarchy[entry_key] = {
                'id': new_id,
                'name': diocese_full_name,
                'type': 'diocese',
                'province': province_name,
                'archdiocese': arch_name
            }
            csv_to_hierarchy[csv_name] = detail_to_hierarchy[entry_key]
            print(f"    ✅ Created '{diocese_full_name}' (id={new_id}, parent={arch_name})")
        else:
            print(f"    Would create '{diocese_full_name}' under '{arch_name}'")
    
    unmatched_csv = still_unmatched

if unmatched_csv:
    print(f"\n  ❌ Still unmatched: {unmatched_csv}")
# ================================================================
# 3. Build county FIPS -> hierarchy diocese ID mapping
# ================================================================
print("\n" + "=" * 70)
print("STEP 3: Build county FIPS → hierarchy diocese ID")
print("=" * 70)

fips_to_hierarchy_id = {}  # FIPS -> hierarchy_id
fips_unmatched = 0
for fips, csv_name in fips_to_diocese.items():
    if csv_name in csv_to_hierarchy:
        fips_to_hierarchy_id[fips] = csv_to_hierarchy[csv_name]['id']
    else:
        fips_unmatched += 1

print(f"  FIPS mapped to hierarchy ID: {len(fips_to_hierarchy_id):,}")
print(f"  FIPS with unmapped diocese: {fips_unmatched}")

# Display unmapped diocese names for manual review
unmapped_dioceses = set(fips_to_diocese.values()) - set(csv_to_hierarchy.keys())
if unmapped_dioceses:
    print(f"\n  Unmapped dioceses ({len(unmapped_dioceses)}):")
    for d in sorted(unmapped_dioceses):
        print(f"    ❌ {d}")

# ================================================================
# 4. Find US Catholic churches NOT in hierarchy
# ================================================================
print("\n" + "=" * 70)
print("STEP 4: Find US Catholic churches not in hierarchy")
print("=" * 70)

# Get Catholic taxonomy IDs
c.execute("SELECT id FROM taxonomy WHERE name LIKE '%Catholic%' OR id IN (14, 86, 92, 100)")
catholic_tax_ids = [r[0] for r in c.fetchall()]
placeholders = ','.join(['?'] * len(catholic_tax_ids))

# Total US Catholic churches
c.execute(f"SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Christian' AND taxonomy_id IN ({placeholders})", catholic_tax_ids)
total_us_catholic = c.fetchone()[0]
print(f"  Total US Catholic churches: {total_us_catholic:,}")

# US Catholic churches already in hierarchy
c.execute(f"""
    SELECT COUNT(*) FROM churches c
    WHERE c.country='US' AND c.faith='Christian' AND c.taxonomy_id IN ({placeholders})
    AND c.rowid IN (SELECT DISTINCT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
""", catholic_tax_ids)
already_in_hierarchy = c.fetchone()[0]
print(f"  Already in hierarchy: {already_in_hierarchy:,}")

# US Catholic churches NOT in hierarchy
c.execute(f"""
    SELECT c.rowid, c.name, c.city, c.state, c.county_fips_5, 
           c.latitude, c.longitude, c.landmark_type
    FROM churches c
    WHERE c.country='US' AND c.faith='Christian' AND c.taxonomy_id IN ({placeholders})
    AND c.rowid NOT IN (SELECT DISTINCT church_id FROM catholic_hierarchy WHERE church_id IS NOT NULL)
    ORDER BY c.state, c.city
""", catholic_tax_ids)
unmatched_churches = c.fetchall()
print(f"  US Catholic NOT in hierarchy: {len(unmatched_churches):,}")

# Split into those with and without county_fips_5
with_fips = [r for r in unmatched_churches if r[4] and r[4].strip()]
without_fips = [r for r in unmatched_churches if not r[4] or not r[4].strip()]
with_gps = [r for r in without_fips if r[5] is not None and r[6] is not None]

print(f"    With county_fips_5: {len(with_fips):,}")
print(f"    Without county_fips_5: {len(without_fips):,}")
print(f"      Of which with GPS: {len(with_gps):,}")

# ================================================================
# 5. Phase 1: Match by county_fips_5
# ================================================================
print("\n" + "=" * 70)
print("PHASE 1: Match by county_fips_5")
print("=" * 70)

phase1_matches = []  # (church_rowid, hierarchy_diocese_id, diocese_name)
phase1_unmatched_fips = 0
phase1_fips_normalized = 0

for r in with_fips:
    church_id = r[0]
    church_state = r[3]  # state abbreviation
    raw_fips = r[4]
    
    # Normalize the FIPS code
    fips = normalize_fips(raw_fips, church_state)
    
    if fips and fips in fips_to_hierarchy_id:
        diocese_id = fips_to_hierarchy_id[fips]
        diocese_name = fips_to_diocese.get(fips, '')
        phase1_matches.append((church_id, diocese_id, diocese_name, fips))
        if fips != raw_fips.strip().zfill(5):
            phase1_fips_normalized += 1
    else:
        phase1_unmatched_fips += 1

print(f"  Matched by FIPS: {len(phase1_matches):,}")
print(f"  FIPS not in map: {phase1_unmatched_fips}")

# ================================================================
# 6. Phase 2: Spatial join for churches without county_fips_5
# ================================================================
print("\n" + "=" * 70)
print("PHASE 2: Spatial join (churches without county_fips_5)")
print("=" * 70)

phase2_matches = []  # (church_rowid, hierarchy_diocese_id, diocese_name, fips)

if with_gps:
    print(f"  Building R-tree spatial index from {len(county_map)} county polygons...")
    
    # Build spatial index from county polygons
    county_polys = []
    county_fips_list = []
    
    for fips, info in county_map.items():
        try:
            geom = wkt.loads(info['geometry'])
            if geom.is_valid:
                county_polys.append(geom)
                county_fips_list.append(fips)
        except Exception as e:
            pass
    
    print(f"  Loaded {len(county_polys):,} valid county polygons")
    
    # Build STRtree
    tree = STRtree(county_polys)
    
    # Query each church point
    spatial_matched = 0
    spatial_unmatched = 0
    
    for i, r in enumerate(with_gps):
        church_id = r[0]
        lat, lon = r[5], r[6]
        
        if lat is None or lon is None:
            spatial_unmatched += 1
            continue
        
        point = Point(lon, lat)
        
        # Query R-tree for candidate county indices (shapely 2.x returns indices)
        candidate_indices = tree.query(point)
        
        matched = False
        for idx in candidate_indices:
            candidate = county_polys[idx]
            if candidate.contains(point):
                fips = county_fips_list[idx]
                
                if fips in fips_to_hierarchy_id:
                    diocese_id = fips_to_hierarchy_id[fips]
                    diocese_name = fips_to_diocese.get(fips, '')
                    phase2_matches.append((church_id, diocese_id, diocese_name, fips))
                    spatial_matched += 1
                    matched = True
                    break
        
        if not matched:
            spatial_unmatched += 1
        
        if (i + 1) % 1000 == 0:
            print(f"    Processed {i+1}/{len(with_gps)} points... (matched: {spatial_matched})")
    
    print(f"  Spatial matched: {spatial_matched:,}")
    print(f"  Spatial unmatched: {spatial_unmatched:,}")

# ================================================================
# 7. Insert into catholic_hierarchy
# ================================================================
print("\n" + "=" * 70)
print("STEP 7: Insert into catholic_hierarchy")
print("=" * 70)

all_matches = phase1_matches + phase2_matches
print(f"  Total matches to insert: {len(all_matches):,}")

# Get church names and locations for the matched churches
all_church_ids = [m[0] for m in all_matches]
insert_data = []

for church_id, diocese_id, diocese_name, fips in all_matches:
    # Get church details
    c.execute("SELECT name, city, state, country FROM churches WHERE rowid = ?", (church_id,))
    church_row = c.fetchone()
    if not church_row:
        continue
    
    church_name = church_row[0] or ''
    church_city = church_row[1] or ''
    church_state = church_row[2] or ''
    church_country = church_row[3] or 'US'
    
    # Get diocese hierarchy info
    c.execute("SELECT name, cath_detail, cath_type, province, archdiocese FROM catholic_hierarchy WHERE id = ?", (diocese_id,))
    diocese_row = c.fetchone()
    if not diocese_row:
        continue
    
    diocese_h_name = diocese_row[0]
    diocese_detail = diocese_row[1]
    diocese_type = diocese_row[2]
    diocese_province = diocese_row[3] or ''
    diocese_archdiocese = diocese_row[4] or ''
    
    insert_data.append((
        diocese_id,              # parent_id
        church_id,               # church_id
        church_name,             # name
        'parish',                # cath_type
        diocese_h_name,          # diocese (full name like "Diocese of X")
        diocese_archdiocese,     # archdiocese
        diocese_province,        # province
        church_city,             # city
        church_state,            # state
        church_country,          # country
        diocese_type,            # parent_cath_type
        'belongs_to_diocese',    # relationship
    ))

print(f"  Prepared {len(insert_data):,} rows for insertion")
print(f"  DRY RUN: {DRY_RUN}")

if not DRY_RUN and insert_data:
    # Insert in chunks
    inserted = 0
    for i in range(0, len(insert_data), CHUNK_SIZE):
        batch = insert_data[i:i + CHUNK_SIZE]
        c.executemany("""
            INSERT INTO catholic_hierarchy 
                (parent_id, church_id, name, cath_type, diocese, archdiocese, province,
                 city, state, country, parent_cath_type, relationship)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        db.commit()
        inserted += len(batch)
    
    # Log provenance
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import gw_db
    gw_db._insert_provenance_log(
        db,
        source=SOURCE,
        script_name='map_catholic_parishes.py',
        started_at=NOW,
        completed_at=NOW,
        churches_updated=inserted,
        churches_inserted=0,
        fields_populated='diocese,archdiocese,province',
        parameters='counties_by_diocese.csv',
        records_attempted=len(all_matches),
        records_matched=inserted,
        status='completed',
        error=None
    )
    
    # Log enrichment changes for each church
    for church_id, _, _, _ in all_matches:
        c.execute("""
            SELECT diocese, archdiocese FROM church_enrichment WHERE church_id = ?
        """, (church_id,))
        existing = c.fetchone()
        
        old_diocese = existing[0] if existing else None
        old_archdiocese = existing[1] if existing else None
        
        # Update church_enrichment
        c.execute("""
            UPDATE church_enrichment 
            SET diocese = ?, archdiocese = ?, catholic_hierarchy_source = 'county_map'
            WHERE church_id = ?
        """, (diocese_h_name, diocese_archdiocese, church_id))
        
        if c.rowcount == 0:
            c.execute("""
                INSERT INTO church_enrichment (church_id, diocese, archdiocese, catholic_hierarchy_source)
                VALUES (?, ?, ?, 'county_map')
            """, (church_id, diocese_h_name, diocese_archdiocese))
    
    db.commit()
    print(f"  ✅ Inserted {inserted:,} parishes into catholic_hierarchy")
    
    # Checkpoint WAL
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print("  ✅ WAL checkpointed")

# ================================================================
# Summary
# ================================================================
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"  Total US Catholic churches: {total_us_catholic:,}")
print(f"  Already in hierarchy: {already_in_hierarchy:,}")
print(f"  Phase 1 (FIPS match): {len(phase1_matches):,} (normalized: {phase1_fips_normalized:,})")
print(f"  Phase 2 (spatial join): {len(phase2_matches):,}")
print(f"  Total newly mapped: {len(all_matches):,}")
print(f"  Remaining unmapped: {len(unmatched_churches) - len(all_matches):,}")

# Show unmatched by state
matched_ids = set(m[0] for m in all_matches)
remaining = [r for r in unmatched_churches if r[0] not in matched_ids]
if remaining:
    print(f"\n  Unmatched by state (top 10):")
    state_counts = {}
    for r in remaining:
        state = r[3] or '??'
        state_counts[state] = state_counts.get(state, 0) + 1
    for state, cnt in sorted(state_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    {state}: {cnt:,}")

db.close()
print("\nDone!")

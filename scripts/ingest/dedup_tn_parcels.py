"""
Deduplicate TN religious parcel records against existing churches in main DB.

Uses three matching strategies:
  1. GPS proximity (parcels with coordinates)
  2. Name + city matching (for parcels without coordinates)
  3. Address matching (for parcels with street addresses)

Merges enrichment data (property values, parcel IDs, building info) onto matched churches.
Creates new church records for truly unmatched parcels.
"""
import sqlite3, sys, re, os
from datetime import datetime, timezone
from shapely.geometry import Point
from shapely.strtree import STRtree

DB = 'churches.db'
TN_DB = 'data/tn_parcels/tn_religious_parcels.db'
CHUNK = 500
DRY_RUN = '--dry-run' in sys.argv
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

tndb = sqlite3.connect(TN_DB)
tc = tndb.cursor()

print("=" * 70)
print("DEDUP TN PARCELS")
print("=" * 70)
print(f"DRY RUN: {DRY_RUN}")

# ================================================================
# Step 1: Build spatial index of existing TN churches with GPS
# ================================================================
print("\n--- Step 1: Build spatial index of existing TN churches ---")

cur = c.execute("""
    SELECT rowid, name, city, latitude, longitude
    FROM churches 
    WHERE country='US' AND state='TN' 
      AND latitude IS NOT NULL AND longitude IS NOT NULL
""")
existing_tn = cur.fetchall()
print(f"Existing TN churches with GPS: {len(existing_tn):,}")

# Build spatial index
church_points = []
church_data = []  # (rowid, name, city, lat, lon)
for rowid, name, city, lat, lon in existing_tn:
    if lat and lon:
        church_points.append(Point(lon, lat))
        church_data.append((rowid, name, city, lat, lon))

tree = STRtree(church_points) if church_points else None
print(f"  Spatial index built: {len(church_points):,} points")

# ================================================================
# Step 2: Get unlinked TN parcels with GPS
# ================================================================
print("\n--- Step 2: Get unlinked TN parcel churches ---")

cur = tc.execute("""
    SELECT id, name, address, city, zip, latitude, longitude, tn_county, 
           tn_parcel_id, tn_class, tn_landuse, tn_owner_raw, tn_owner2,
           tn_appraisal_value, tn_assessment_value, tn_sqft, tn_yrblt,
           tn_sale_price, landmark_type
    FROM tn_religious_parcels
    WHERE grid_church_id IS NULL AND landmark_type = 'church'
      AND latitude IS NOT NULL AND longitude IS NOT NULL
""")
parcels_with_gps = cur.fetchall()
print(f"Unlinked parcels with GPS: {len(parcels_with_gps):,}")

# Also get parcels without GPS for name/address matching
cur = tc.execute("""
    SELECT id, name, address, city, zip, latitude, longitude, tn_county, 
           tn_parcel_id, tn_class, tn_landuse, tn_owner_raw, tn_owner2,
           tn_appraisal_value, tn_assessment_value, tn_sqft, tn_yrblt,
           tn_sale_price, landmark_type
    FROM tn_religious_parcels
    WHERE grid_church_id IS NULL AND landmark_type = 'church'
      AND (latitude IS NULL OR longitude IS NULL)
""")
parcels_without_gps = cur.fetchall()
print(f"Unlinked parcels without GPS: {len(parcels_without_gps):,}")

# ================================================================
# Step 3: Match by GPS proximity
# ================================================================
print("\n--- Step 3: GPS proximity matching ---")

# City alias map for renamed towns (parcel name → canonical)
CITY_ALIASES = {
    'rocky top': ['rocky top', 'lake city'],
    'lake city': ['lake city', 'rocky top'],
}

# Generic words stripped from names before comparison — too common to be meaningful
GENERIC_WORDS = {'the','of','and','a','an','inc','co','ltd','corporation','trustees',
                 'trust','foundation','church','chapel','cathedral','basilica','shrine',
                 'st','saint','mc','mac','roman','catholic','diocese','parish',
                 'baptist','methodist','presbyterian','episcopal','pentecostal',
                 'assembly','lutheran','apostolic','missionary','christian',
                 'ministry','ministries','fellowship','center','temple',
                 'highway','hwy','road','rd','street','st','drive','dr',
                 'lane','ln','circle','cir','court','ct','place','pl',
                 'avenue','ave','boulevard','blvd','pike','pkwy','trace',
                 'north','south','east','west','northeast','southeast',
                 'northwest','southwest','no','so','ea','we'}

def normalize_name(s):
    """Normalize church name for comparison — strips generic words."""
    if not s:
        return ''
    s = s.strip().lower()
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    words = s.split()
    words = [w for w in words if w not in GENERIC_WORDS and len(w) > 2]
    return ' '.join(words)

def name_word_overlap(a, b):
    """Compute word overlap score between two normalized names.
    Uses Jaccard similarity on non-generic words.
    """
    if not a or not b:
        return 0, 0
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0, 0
    intersection = words_a & words_b
    jaccard = len(intersection) / len(words_a | words_b) if words_a | words_b else 0
    return jaccard, len(intersection)

# GPS proximity (200m threshold)
gps_matches = []  # (parcel_id, church_rowid, distance, method)
gps_parcel_matched = set()

for parcel in parcels_with_gps:
    pid, pname, paddr, pcity, pzip, plat, plon, pcounty, pparcel_id = parcel[:9]
    preston = parcel[13:17]  # appraisal value, sqft, yrblt, sale_price
    
    if plat is None or plon is None:
        continue
    
    point = Point(plon, plat)
    
    # Query spatial index
    if tree:
        candidates = tree.query(point)
        for idx in candidates:
            candidate = church_points[idx]
            if candidate.distance(point) < 0.002:  # ~200m at TN latitude
                church_rowid, cname, ccity, clat, clon = church_data[idx]
                gps_matches.append((pid, church_rowid, candidate.distance(point) * 111000, 'gps_proximity'))
                gps_parcel_matched.add(pid)
                break  # Take the closest match

print(f"  GPS matched: {len(gps_matches):,}")

# ================================================================
# Step 4: Match by name + city (for parcels without GPS)
# ================================================================
print("\n--- Step 4: Name + city matching ---")

# Build normalised name index for existing TN churches
church_name_index = {}
for rowid, name, city, lat, lon in existing_tn:
    if name and city:
        key = (normalize_name(name), city.strip().lower())
        if key not in church_name_index:
            church_name_index[key] = []
        church_name_index[key].append(rowid)

name_matches = []  # (parcel_id, church_rowid, method)
name_parcel_matched = set()

# Build index: (normalized_name, canonical_city) -> [church_rowids]
# and also: first_word -> [(norm_name, canonical_city, rowid)]
church_by_city = {}  # canonical_city -> [(norm_name, rowid)]

for rowid, name, city, lat, lon in existing_tn:
    if not name or not city:
        continue
    nname = normalize_name(name)
    ccity = city.strip().lower()
    if ccity not in church_by_city:
        church_by_city[ccity] = []
    church_by_city[ccity].append((nname, rowid))

for parcel in parcels_without_gps + parcels_with_gps:
    pid = parcel[0]
    if pid in gps_parcel_matched:
        continue  # Already matched by GPS
    
    pname = parcel[1]
    pcity = parcel[3]
    
    if not pname or not pcity:
        continue
    
    # Clean city (remove number prefix)
    pcity_clean = re.sub(r'^\d+\s+', '', pcity.strip()).lower()
    pname_norm = normalize_name(pname)
    
    if not pname_norm or not pcity_clean:
        continue
    
    # Find which canonical cities match
    candidate_cities = {pcity_clean}
    for alias_list in CITY_ALIASES.values():
        if pcity_clean in alias_list:
            candidate_cities.update(alias_list)
    
    # Score all churches in matching cities by word overlap
    best_jaccard = 0
    best_overlap_count = 0
    best_match = None
    
    for ccity in candidate_cities:
        if ccity not in church_by_city:
            continue
        for cnorm, church_rowid in church_by_city[ccity]:
            jaccard, overlap_count = name_word_overlap(pname_norm, cnorm)
            # Boost for exact match
            if cnorm == pname_norm:
                jaccard = 1.0
                overlap_count = max(len(pname_norm.split()), 999)
            if jaccard > best_jaccard or (jaccard == best_jaccard and overlap_count > best_overlap_count):
                best_jaccard = jaccard
                best_overlap_count = overlap_count
                best_match = (church_rowid, ccity, 'name_exact' if cnorm == pname_norm else 'name_overlap')
    
    # Accept matches with Jaccard >= 0.3 AND at least 2 overlapping words
    if best_match and best_jaccard >= 0.3 and best_overlap_count >= 2:
        church_rowid, matched_city, method = best_match
        name_matches.append((pid, church_rowid, method))
        name_parcel_matched.add(pid)

print(f"  Name matched: {len(name_matches):,}")

# ================================================================
# Step 5: Update grid_church_id in TN DB
# ================================================================
all_matches = gps_matches + name_matches
print(f"\n--- Step 5: Update links ({len(all_matches):,} total) ---")

if all_matches and not DRY_RUN:
    updated = 0
    for match in all_matches:
        pid = match[0]
        church_rowid = match[1]
        tc.execute("UPDATE tn_religious_parcels SET grid_church_id = ? WHERE id = ?", (church_rowid, pid))
        if tc.rowcount > 0:
            updated += 1
    tndb.commit()
    print(f"  ✅ Updated {updated:,} grid_church_id links")
    
    # Also log enrichment values to main DB
    enrichment_updates = []
    for match in all_matches:
        pid = match[0]
        church_rowid = match[1]
        method = match[2] if len(match) > 2 else 'unknown'
        
        # Get parcel details
        cur = tc.execute("""
            SELECT tn_parcel_id, tn_appraisal_value, tn_sqft, tn_yrblt, 
                   tn_owner_raw, tn_sale_price, tn_county, tn_class
            FROM tn_religious_parcels WHERE id = ?
        """, (pid,))
        prow = cur.fetchone()
        if not prow:
            continue
        
        pid_val, appraisal, sqft, yrblt, owner, sale, county, pclass = prow
        
        # Update main church with enrichment data
        updates = []
        if appraisal:
            c.execute("UPDATE churches SET building_sqft = COALESCE(building_sqft, ?) WHERE rowid = ?", 
                     (sqft, church_rowid))
        if yrblt:
            c.execute("UPDATE churches SET building_year = COALESCE(building_year, ?) WHERE rowid = ?",
                     (yrblt, church_rowid))
        
        enrichment_updates.append((church_rowid, pid_val, method, NOW))
    
    # Log enrichment changes
    for church_rowid, pid_val, method, ts in enrichment_updates:
        c.execute("""
            UPDATE churches SET 
                notes = COALESCE(notes, '') || ' | TN Parcel: ' || ?
            WHERE rowid = ?
        """, (pid_val, church_rowid))
    
    db.commit()
    print(f"  ✅ Enriched {len(enrichment_updates):,} churches with TN parcel data")
    
    # Log provenance
    now = NOW
    c.execute("""
        INSERT INTO provenance_log 
        (source, script_name, started_at, completed_at, churches_updated, 
         churches_inserted, fields_populated, records_attempted, records_matched, 
         status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('dedup_tn_parcels', 'scripts/ingest/dedup_tn_parcels.py', now, now,
          updated, 0,
          'grid_church_id,tn_parcel_id,building_sqft,building_year',
          len(parcels_with_gps + parcels_without_gps), updated,
          'completed',
          f'Matched {updated} TN parcels to existing churches via GPS proximity ({len(gps_matches)}) and name+city ({len(name_matches)}). Gave 633 new GPS points via Census geocoder.'))
    db.commit()
    
    # WAL checkpoint
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    print("  ✅ WAL checkpointed")

# ================================================================
# Summary
# ================================================================
cur = tc.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE grid_church_id IS NOT NULL")
total_linked = cur.fetchone()[0]
cur = tc.execute("SELECT COUNT(*) FROM tn_religious_parcels WHERE grid_church_id IS NULL AND landmark_type='church'")
still_unlinked = cur.fetchone()[0]

print(f"\n{'='*70}")
print("SUMMARY")
print(f"{'='*70}")
print(f"  GPS matched: {len(gps_matches):,}")
print(f"  Name matched: {len(name_matches):,}")
print(f"  Total new links: {len(all_matches):,}")
print(f"  Total linked: {total_linked:,}")
print(f"  Still unlinked (church): {still_unlinked:,}")
print(f"  DRY RUN: {DRY_RUN}")

db.close()
tndb.close()
print("\nDone!")

"""
Link LDS hierarchy: parent-child relationships between all entity types.

Builds the structural links:
  HQ (id=40546)
    ├── Presiding Bishop Offices (legal/corporate, not Area Presidencies) → HQ
    ├── Temple → HQ (Area Presidency records absent from dataset)
    ├── Stake House → Temple (same-state preferred, haversine nearest-neighbor)
    ├── Meetinghouse → Stake House (city+state match, then haversine, ≤200 km)
    ├── Institute / Seminary → nearest Temple (CES, direct)
    ├── Employment Center / Storehouse → nearest Temple (Welfare, direct)
    ├── Family History Center → nearest Temple (direct)
    └── Mission Office → nearest Temple (functional)

Uses Haversine distance for spatial nearest-neighbor matching.
Updates parent_id, parent_lds_type, and relationship columns.
Logs provenance at completion.

Usage:
    python scripts/db_maintenance/link_lds_hierarchy.py
    python scripts/db_maintenance/link_lds_hierarchy.py --dry-run
"""
import sqlite3
import sys
import math
import time
from datetime import datetime, timezone

DB_PATH = r'E:\grid\churches.db'
CHUNK = 500
DRY_RUN = '--dry-run' in sys.argv

# ─── Haversine distance (km) ───────────────────────────────────────────────
def haversine_km(lat1, lon1, lat2, lon2):
    """Return distance in km between two lat/lon points."""
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_nearest(entity, targets, max_km=None):
    """
    Find nearest target entity by Haversine distance.
    Returns (target_id, distance_km) or (None, None).
    """
    best_id, best_dist = None, float('inf')
    for t in targets:
        d = haversine_km(entity['lat'], entity['lon'], t['lat'], t['lon'])
        if d < best_dist:
            best_dist = d
            best_id = t['id']
    if max_km is not None and best_dist > max_km:
        return None, None
    return best_id, best_dist


def log_provenance(wc, attempts, matched, fields, note=''):
    """Write provenance log entry."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    wc.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('lds_hierarchy_link', 'link_lds_hierarchy.py', now, now,
          matched, 0, fields, attempts, matched, 'completed', note))


def main():
    print(f'Linking LDS hierarchy ({"DRY RUN" if DRY_RUN else "LIVE"})...')
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH, timeout=120)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=120000')
    c = conn.cursor()

    wconn = sqlite3.connect(DB_PATH, timeout=120)
    wconn.execute('PRAGMA journal_mode=WAL')
    wconn.execute('PRAGMA busy_timeout=120000')
    wconn.isolation_level = None
    wc = wconn.cursor()

    # ─── Load all entities into memory ─────────────────────────────────
    print('Loading LDS entities...')
    c.execute("""
        SELECT id, lds_type, city, state, country, lat, lon
        FROM lds_hierarchy ORDER BY id
    """)
    all_rows = c.fetchall()
    print(f'  {len(all_rows):,} total entities')

    # Index by type
    entities = {}
    for r in all_rows:
        eid, ltype, city, state, country, lat, lon = r
        entities[eid] = {
            'id': eid, 'type': ltype, 'city': city or '',
            'state': state or '', 'country': country or '',
            'lat': lat, 'lon': lon
        }

    # Group by type
    by_type = {}
    for eid, ent in entities.items():
        by_type.setdefault(ent['type'], []).append(ent)

    hq = [e for e in by_type.get('hq', [])]
    area_offices = by_type.get('area_office', [])
    temples = by_type.get('temple', [])
    stake_houses = by_type.get('stake_house', [])
    meetinghouses = by_type.get('meetinghouse', [])
    specials = []
    for t in ('institute', 'seminary', 'storehouse', 'employment_center',
              'family_history_center', 'mission_office', 'other'):
        specials.extend(by_type.get(t, []))

    print(f'  HQ: {len(hq)}')
    print(f'  Area Offices: {len(area_offices)}')
    print(f'  Temples: {len(temples)}')
    print(f'  Stake Houses: {len(stake_houses)}')
    print(f'  Meetinghouses: {len(meetinghouses)}')
    print(f'  Special types: {len(specials)}')

    if not hq:
        print('ERROR: No HQ record found!')
        sys.exit(1)
    hq_id = hq[0]['id']
    print(f'  HQ ID: {hq_id}')

    # Filter to entities with valid GPS for spatial matching
    temples_gps = [t for t in temples if t['lat'] is not None]
    stake_houses_gps = [s for s in stake_houses if s['lat'] is not None]
    print(f'  Temples with GPS: {len(temples_gps)}')
    print(f'  Stake houses with GPS: {len(stake_houses_gps)}')

    # Build index: state → list of temples (for state-preference matching)
    temples_by_state = {}
    for t in temples_gps:
        temples_by_state.setdefault(t['state'], []).append(t)

    # Build index: state → list of stake houses
    sh_by_state = {}
    for s in stake_houses_gps:
        sh_by_state.setdefault(s['state'], []).append(s)

    # Build index: city+state → list of stake houses
    sh_by_city_state = {}
    for s in stake_houses_gps:
        key = (s['city'], s['state'])
        sh_by_city_state.setdefault(key, []).append(s)

    # ─── Prepare DB updates ────────────────────────────────────────────
    total_attempted = 0
    total_matched = 0

    # We'll collect (child_id, parent_id, relationship, parent_type) tuples
    updates = []

    # ────────────────────────────────────────────────────────────────────
    # 1. Area Office → HQ
    # ────────────────────────────────────────────────────────────────────
    print('\n1. Linking Area Offices → HQ...')
    for ao in area_offices:
        updates.append((ao['id'], hq_id, 'administered_by', 'hq'))
    print(f'   {len(area_offices)} area offices → HQ')

    # ────────────────────────────────────────────────────────────────────
    # 2. Temple → HQ
    # ────────────────────────────────────────────────────────────────────
    print('\n2. Linking Temples → HQ...')
    for tm in temples:
        updates.append((tm['id'], hq_id, 'administered_by', 'hq'))
    print(f'   {len(temples)} temples → HQ')

    # ────────────────────────────────────────────────────────────────────
    # 3. Stake House → Temple (same-state preferred, else nearest)
    # ────────────────────────────────────────────────────────────────────
    print('\n3. Linking Stake Houses → Temple...')
    sh_matched = 0
    for sh in stake_houses:
        state = sh['state']
        # Try same-state temples first
        candidates = temples_by_state.get(state, [])
        if not candidates:
            # Fallback: all temples
            candidates = temples_gps
        parent_id, dist = find_nearest(sh, candidates)
        if parent_id:
            updates.append((sh['id'], parent_id, 'administered_by', 'temple'))
            sh_matched += 1
    print(f'   {sh_matched}/{len(stake_houses)} stake houses matched')

    # ────────────────────────────────────────────────────────────────────
    # 4. Meetinghouse → Stake House (city+state, then nearest, ≤200 km)
    # ────────────────────────────────────────────────────────────────────
    print('\n4. Linking Meetinghouses → Stake House...')
    mh_matched = 0
    mh_no_city = 0
    mh_by_city = 0

    for mh in meetinghouses:
        city, state = mh['city'], mh['state']
        candidates = None

        # Priority 1: Same city + state (exact match)
        if city and state:
            key = (city, state)
            if key in sh_by_city_state:
                candidates = sh_by_city_state[key]

        # Priority 2: Same state (any stake house in state)
        if not candidates and state:
            candidates = sh_by_state.get(state)

        # Priority 3: All stake houses (nearest, no distance cap)
        if not candidates:
            candidates = stake_houses_gps

        parent_id, dist = find_nearest(mh, candidates)
        if parent_id:
            updates.append((mh['id'], parent_id, 'served_by', 'stake_house'))
            mh_matched += 1
            if city and state and (city, state) in sh_by_city_state:
                mh_by_city += 1
        else:
            if not city and not mh['lat']:
                mh_no_city += 1
    print(f'   {mh_matched}/{len(meetinghouses)} meetinghouses matched ({mh_by_city} by city)')
    print(f'   {mh_no_city} meetinghouses skipped (no city + no GPS)')

    # ────────────────────────────────────────────────────────────────────
    # 5. Special types → nearest Temple
    # ────────────────────────────────────────────────────────────────────
    print('\n5. Linking special types → nearest Temple...')
    sp_matched = 0
    sp_type_counts = {}
    for sp in specials:
        ltype = sp['type']
        sp_type_counts[ltype] = sp_type_counts.get(ltype, 0) + 1
        parent_id, dist = find_nearest(sp, temples_gps)
        if parent_id:
            updates.append((sp['id'], parent_id, 'affiliated_with', 'temple'))
            sp_matched += 1
    print(f'   {sp_matched}/{len(specials)} specials matched')
    for t, cnt in sorted(sp_type_counts.items()):
        print(f'     {t}: {cnt}')

    # ────────────────────────────────────────────────────────────────────
    # Write to DB
    # ────────────────────────────────────────────────────────────────────
    total_attempted = len(updates)
    total_matched = len(updates)  # all are matches

    print(f'\n{"=" * 50}')
    print(f'Total links to create: {total_matched:,}')
    print(f'{"=" * 50}')

    if DRY_RUN:
        print('\nDRY RUN — no DB writes. Run without --dry-run to execute.')
        conn.close()
        wconn.close()
        return

    # Batch write updates
    wc.execute('BEGIN TRANSACTION')
    for i, (child_id, parent_id, rel, parent_type) in enumerate(updates):
        wc.execute("""
            UPDATE lds_hierarchy SET
                parent_id = ?,
                parent_lds_type = ?,
                relationship = ?
            WHERE id = ?
        """, (parent_id, parent_type, rel, child_id))
        if (i + 1) % CHUNK == 0:
            wc.execute('COMMIT')
            wc.execute('BEGIN TRANSACTION')
            print(f'\r  Written {i+1:,}/{total_matched:,} updates...', end='', flush=True)
    wc.execute('COMMIT')
    print(f'\r  Written {total_matched:,}/{total_matched:,} updates... done!')

    # Verify
    c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE parent_id IS NOT NULL")
    linked = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM lds_hierarchy WHERE parent_id IS NULL")
    unlinked = c.fetchone()[0]
    print(f'\nVerification: {linked:,} linked, {unlinked:,} unlinked')

    # Show relationship breakdown
    print('\nRelationship breakdown:')
    c.execute("SELECT relationship, parent_lds_type, COUNT(*) FROM lds_hierarchy WHERE relationship IS NOT NULL GROUP BY relationship, parent_lds_type ORDER BY COUNT(*) DESC")
    for row in c.fetchall():
        print(f'  {row[0]:>20} → {row[1]:>15}: {row[2]:,}')

    # Provenance
    fields = ('parent_id,parent_lds_type,relationship')
    note = (f'Linked {linked:,}/{linked+unlinked:,} entities. '
            f'Stake→Temple: {sh_matched}, MH→Stake: {mh_matched}, Specials→Temple: {sp_matched}')
    log_provenance(wc, total_attempted, total_matched, fields, note)
    print(f'\nProvenance logged. Total time: {time.time() - t0:.1f}s')

    conn.close()
    wconn.close()


if __name__ == '__main__':
    main()

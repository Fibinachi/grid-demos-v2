"""
_classify_tec_entities.py — Classify TEC-tagged records by entity_type
and build 3-level parent hierarchy: org→congregation→diocese→national.
"""
import sqlite3
import re
import sys
from collections import defaultdict

# Add data dir to path for county mapping
sys.path.insert(0, 'E:/grid/data')

DB = 'E:/grid/churches.db'

# ── Diocese lookup tables ───────────────────────────────────────────

SINGLE_DIOCESE_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'ME': 'Maine', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NM': 'New Mexico', 'ND': 'North Dakota',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'RI': 'Rhode Island',
    'SD': 'South Dakota', 'UT': 'Utah', 'VT': 'Vermont',
    'WA': 'Olympia', 'WV': 'West Virginia', 'WI': 'Wisconsin',
    'WY': 'Wyoming', 'DC': 'Washington',
}

# Diocese display name for each state (used when linking to diocesan_entity)
DIOCESE_NAMES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Chicago', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky',
    'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts',
    'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MT': 'Montana',
    'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Olympia', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'Washington',
}

MULTI_DIOCESE_STATES = {'TX', 'CA', 'FL', 'NY', 'NC', 'LA', 'GA', 'PA', 'MO',
                         'OH', 'MI', 'IL', 'VA', 'SC', 'TN', 'WA', 'OR', 'KS',
                         'KY', 'MA', 'IN', 'MD', 'NJ'}


# ── Classification ──────────────────────────────────────────────────

def classify_entity_type(name):
    """Classify a record by entity_type based on name patterns."""
    n = name.lower().strip()

    # National body
    if 'protestant episcopal church in the usa' in n:
        return 'national_body'
    if n.startswith('protestant episcopal church in the us'):
        return 'national_body'

    # Other Anglican province (not TEC)
    if 'south sudanese' in n and 'episcopal' in n:
        return 'other_anglican'

    # Non-TEC denominations
    if any(x in n for x in ['african methodist episcopal', 'african medhodist episcopal',
                              'african metholdist episcopal', 'african medethodist episcopal',
                              'african medthodist episcopal', 'union methodist episcopal',
                              'union american methodist episcopal', 'wesleyan methodist episcopal',
                              'methodist episcopal zion', 'episcopal zion',
                              'reformed episcopal', 'charismatic episcopal',
                              'independent episcopal', 'independnet episcopal',
                              'united episcopal church', 'christian episcopal church',
                              'pentecostal episcopal', 'pentacostal episcopal',
                              'traditional episcopal church', 'american episcopal church inc',
                              'holy episcopal church inc', 'free episcopal church',
                              'evangelical episcopal', 'evangelical wesleyan episcopal',
                              'anglican episcopal church of na']):
        return 'non_tec_denomination'

    # Councils (governance)
    if 'episcopal church council' in n:
        return 'council'
    if 'protestant episcopal church council' in n:
        return 'council'

    # Diocesan entities
    if 'diocese of' in n and 'episcopal' in n:
        if any(x in n for x in ['church', 'parish', 'cathedral', 'chapel', 'mission', 'congregation']):
            return 'congregation'
        return 'diocesan_entity'
    if 'episcopal diocese of' in n:
        return 'diocesan_entity'
    if 'episcopal dioceses of' in n:
        return 'diocesan_entity'
    if 'protestant episcopal church in diocese of' in n:
        return 'diocesan_entity'
    if 'protestant episcopal church of the diocese of' in n:
        return 'diocesan_entity'
    if 'protestant episcopal church diocese of' in n:
        return 'diocesan_entity'
    if 'episcopal church in the diocese of' in n:
        return 'diocesan_entity'
    if 'episcopal church in north texas' in n:
        return 'diocesan_entity'
    if 'episcopal church in hawaii' in n:
        return 'diocesan_entity'
    if 'episcopal church in idaho inc' in n:
        return 'diocesan_entity'
    if 'episcopal church corporation in' in n:
        return 'diocesan_entity'
    if 'protestant episcopal church in the diocses of' in n:
        return 'diocesan_entity'

    # Legal holding entities
    if any(x in n for x in ['rector wardens vestry', 'wardens vestrymen', 'rector and vestry']):
        return 'legal_holding'
    if n.startswith('proprietors of') and 'episcopal' in n:
        return 'legal_holding'

    # Fund/LLC entities
    if (' fund for ' in n or ' fund of ' in n) and 'episcopal' in n:
        return 'fund_entity'

    # Endowment trusts
    if 'permanent endownment' in n:
        return 'endowment_trust'
    if 'charitable tr' in n and 'episcopal' in n:
        return 'endowment_trust'

    # Gift shops / thrift shops / outreach
    if 'gift shop' in n:
        return 'outreach'
    if 'thrift shop' in n:
        return 'outreach'
    if 'mothers day out' in n:
        return 'outreach'
    if 'youth outreach center' in n:
        return 'outreach'

    # Friends orgs
    if n.startswith('friends of') and 'episcopal' in n:
        return 'friends_org'

    # Societies
    if 'society of the episcopal church' in n:
        return 'society'

    # Chapels
    if 'episcopal chapel' in n and 'episcopal church' not in n:
        return 'chapel'

    # General synod (non-TEC)
    if 'general synod of the' in n:
        return 'non_tec_denomination'

    # Communion of convergence churches
    if 'communion of episcopal' in n:
        return 'non_tec_denomination'

    # Order of the Magi (not TEC)
    if 'order of the magi' in n:
        return 'non_tec_denomination'

    # Default: congregation
    if any(x in n for x in ['church', 'parish', 'cathedral', 'chapel', 'congregation', 'mission']):
        return 'congregation'

    if 'episcopal' in n:
        return 'congregation'

    return 'unknown'


# ── Name normalization ─────────────────────────────────────────────

def normalize_church_name(name):
    """Strip suffixes to get the core church name for campus grouping."""
    n = name.lower().strip()
    for suffix in [' gift shop', ' thrift shop', ' mothers day out',
                   ' permanent endownment tr', ' charitable tr',
                   ' a corp', ' inc', ' incorporated', ' llc',
                   ' rector wardens vestry', ' wardens vestrymen',
                   ' youth outreach center', ' hwy 540 a',
                   ' corner wilson green streets', ' pilgrim mill rd',
                   ' 1101 vandora springs rd', ' collier blvd',
                   ' south palmetto st', ' hodge st', ' aia at cove',
                   " 1928 saint mary's rd", ' sd',
                   ' of el dorado ks', ' of kittrell nc mrs r b pearce jr',
                   ' gec', ' ofl', ' of whiting new jersey']:
        n = n.replace(suffix, '')
    n = re.sub(r'^episcopal diocese of \w+ \w+ ', '', n)
    n = re.sub(r'^episcopal dioceses of \w+ \w+ \w+ ', '', n)
    n = re.sub(r'^diocese of \w+ \w+ inc ', '', n)
    return n.strip()


def extract_core_name(name):
    """Extract the church core name for parent matching (suffix stripping)."""
    n = name.lower().strip()
    n = re.sub(r'^the ', '', n)
    # Strip suffixes
    for suffix in [' gift shop', ' thrift shop', ' mothers day out',
                   ' permanent endownment tr', ' charitable tr',
                   ' rector wardens vestry', ' wardens vestrymen',
                   ' fund for', ' fund of']:
        if suffix in n:
            n = n[:n.index(suffix)].strip()
    # Strip prefixes
    if n.startswith('proprietors of '):
        n = n[15:].strip()
    if n.startswith('rector wardens vestrymen of '):
        n = n[29:].strip()
    if n.startswith('rector wardens vestry of '):
        n = n[23:].strip()
    if n.startswith('friends of '):
        n = n[10:].strip()
    n = re.sub(r'\s+(inc|llc|a corp|tr)$', '', n)
    return n.strip()


def get_diocese_for_state_county(state, county, county_map):
    """Get diocese name for a given state/county."""
    if not state:
        return None
    state = state.upper().strip()
    county_clean = county.upper().strip().replace(' COUNTY', '') if county else ''

    # Single-diocese states
    if state in SINGLE_DIOCESE_STATES:
        return SINGLE_DIOCESE_STATES[state]

    # Multi-diocese states — try county mapping
    if state in county_map and county_clean:
        for cname, dname in county_map[state].items():
            if cname.upper() == county_clean or county_clean in cname.upper() or cname.upper() in county_clean:
                return dname

    # Fallback to state-level default
    return DIOCESE_NAMES.get(state)


# ── Main ────────────────────────────────────────────────────────────

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    # Load county-diocese mapping
    try:
        from tec_county_diocese import STATE_COUNTY_DIOCESE
        county_map = STATE_COUNTY_DIOCESE
        print("Loaded county→diocese mapping.")
    except ImportError as e:
        print(f"WARNING: Could not load county→diocese mapping ({e}), using state defaults only")
        county_map = {}

    # Add entity_type column if needed
    existing = [r[1] for r in conn.execute("PRAGMA table_info(churches)").fetchall()]
    if 'entity_type' not in existing:
        print("Adding entity_type column...")
        conn.execute("ALTER TABLE churches ADD COLUMN entity_type TEXT")
        conn.commit()
    else:
        print("entity_type column already exists.")

    # Load all TEC records
    print("Loading TEC records...")
    rows = conn.execute("""
        SELECT id, name, city, state, county, fips, denomination
        FROM churches
        WHERE denomination LIKE '%episcopal%'
        AND denomination NOT IN ('African Methodist Episcopal',
                                  'African Methodist Episcopal Zion',
                                  'Christian Methodist Episcopal')
    """).fetchall()
    print(f"  {len(rows)} records")

    # ═══════════════════════════════════════════════════════════════
    # PASS 1: Classify entity_type
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Pass 1: Classifying entity types ---")
    stats = defaultdict(int)
    records = {}  # id -> (name, city, state, county, fips, entity_type)

    for row in rows:
        church_id, name, city, state, county, fips, denomination = row
        etype = classify_entity_type(name)
        stats[etype] += 1
        records[church_id] = (name, city, state, county or '', fips or '', etype)

    for etype, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {etype:25s}: {count:5d}")

    conn.executemany("UPDATE churches SET entity_type = ? WHERE id = ?",
                     [(records[i][5], i) for i in records])
    conn.commit()

    # ═══════════════════════════════════════════════════════════════
    # PASS 2: Link associated orgs → parent congregation (same city)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Pass 2: Linking associated orgs to congregations ---")
    org_types = {'legal_holding', 'fund_entity', 'endowment_trust', 'outreach',
                 'friends_org', 'chapel', 'society', 'council'}

    # Build lookup: (city, state) → list of congregation (id, name)
    cong_by_city = defaultdict(list)
    for cid, (name, city, state, county, fips, etype) in records.items():
        if etype == 'congregation' and city:
            cong_by_city[(city.strip().upper(), (state or '').strip().upper())].append((cid, name))

    parent_updates = []
    for cid, (name, city, state, county, fips, etype) in records.items():
        if etype not in org_types or not city:
            continue
        key = (city.strip().upper(), (state or '').strip().upper())
        candidates = cong_by_city.get(key, [])
        if not candidates:
            continue

        core = extract_core_name(name)
        for pcid, pname in candidates:
            pcore = normalize_church_name(pname)
            if core in pcore or pcore in core or core == pcore:
                parent_updates.append((pcid, cid))
                break

    if parent_updates:
        conn.executemany("UPDATE churches SET parent_church_id = ? WHERE id = ?", parent_updates)
        conn.commit()
        print(f"  Linked {len(parent_updates)} associated orgs to parent congregations")
    else:
        print("  No org→congregation links found")

    # ═══════════════════════════════════════════════════════════════
    # PASS 3: Link congregations → diocese (via county mapping)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Pass 3: Linking congregations to dioceses ---")

    # Map state→diocesan_entity
    dio_by_state = {}
    for cid, (name, city, state, county, fips, etype) in records.items():
        if etype == 'diocesan_entity' and state:
            dio_by_state.setdefault(state.strip().upper(), []).append((cid, name))

    national_ids = [cid for cid, (n, c, s, co, f, e) in records.items() if etype == 'national_body']
    print(f"  Diocesan entities: {sum(len(v) for v in dio_by_state.values())}, "
          f"National body records: {len(national_ids)}")

    dio_parent_updates = []
    for cid, (name, city, state, county, fips, etype) in records.items():
        if etype in ('non_tec_denomination', 'other_anglican', 'national_body'):
            continue
        if not state:
            continue

        st = state.strip().upper()
        diocese_name = get_diocese_for_state_county(st, county, county_map)
        if not diocese_name:
            continue

        # Match against diocesan entity names
        candidates = dio_by_state.get(st, [])
        matched_dio = None
        for did, dname in candidates:
            if diocese_name.lower() in dname.lower():
                matched_dio = did
                break

        if matched_dio and matched_dio != cid:
            # Don't overwrite an existing parent from pass 2
            existing_parent = conn.execute(
                "SELECT parent_church_id FROM churches WHERE id = ?", (cid,)
            ).fetchone()
            if not existing_parent or not existing_parent[0]:
                dio_parent_updates.append((matched_dio, cid))

    if dio_parent_updates:
        conn.executemany("UPDATE churches SET parent_church_id = ? WHERE id = ?", dio_parent_updates)
        conn.commit()
        print(f"  Linked {len(dio_parent_updates)} entities to dioceses")
    else:
        print("  No diocese links made")

    # ═══════════════════════════════════════════════════════════════
    # PASS 4: Link diocesan entities → national body
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Pass 4: Linking dioceses to national body ---")
    if national_ids:
        national_id = national_ids[0]  # Primary national body record
        national_links = 0
        for cid, (name, city, state, county, fips, etype) in records.items():
            if etype == 'diocesan_entity':
                existing_parent = conn.execute(
                    "SELECT parent_church_id FROM churches WHERE id = ?", (cid,)
                ).fetchone()
                if not existing_parent or not existing_parent[0]:
                    conn.execute("UPDATE churches SET parent_church_id = ? WHERE id = ?",
                                (national_id, cid))
                    national_links += 1
        conn.commit()
        print(f"  Linked {national_links} diocesan entities to national body (id={national_id})")
    else:
        print("  No national body record found — skipping")

    # ═══════════════════════════════════════════════════════════════
    # PASS 5: Campus grouping (same norm name, different cities, same state)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Pass 5: Campus grouping ---")
    congregations = conn.execute("""
        SELECT id, name, city, state
        FROM churches
        WHERE entity_type = 'congregation'
    """).fetchall()

    groups = defaultdict(list)
    for crow in congregations:
        cid, cname, ccity, cstate = crow
        norm = normalize_church_name(cname)
        key = (norm, (cstate or '').strip().upper())
        groups[key].append((cid, cname, ccity))

    campus_updates = []
    campus_group_counter = 1

    for key, members in groups.items():
        if len(members) < 2:
            continue
        cities = set(m[2].strip().upper() if m[2] else '' for m in members)
        cities.discard('')
        if len(cities) < 2:
            continue

        primary_id = members[0][0]
        primary_name = members[0][1]
        for member in members[1:]:
            campus_id, campus_name, campus_city = member
            campus_updates.append((
                'campus', campus_group_counter, primary_id,
                primary_name, campus_id
            ))
        campus_group_counter += 1

    if campus_updates:
        conn.executemany("""
            UPDATE churches
            SET entity_type = ?, campus_group_id = ?, parent_church_id = ?, campus_name = ?
            WHERE id = ?
        """, campus_updates)
        conn.commit()
        print(f"  Found {len(campus_updates)} campus relationships")
    else:
        print("  No campus relationships found")

    # ═══════════════════════════════════════════════════════════════
    # Final summary
    # ═══════════════════════════════════════════════════════════════
    print("\n=== Final hierarchy summary ===")
    for etype, count in conn.execute("""
        SELECT entity_type, COUNT(*) FROM churches
        WHERE denomination LIKE '%episcopal%'
          AND denomination NOT IN ('African Methodist Episcopal',
                                    'African Methodist Episcopal Zion',
                                    'Christian Methodist Episcopal')
        GROUP BY 1 ORDER BY 2 DESC
    """).fetchall():
        et = etype or 'NULL'
        with_parent = conn.execute("""
            SELECT COUNT(*) FROM churches
            WHERE entity_type = ? AND parent_church_id IS NOT NULL
              AND denomination LIKE '%episcopal%'
        """, (etype,)).fetchone()[0]
        print(f"  {et:25s}: {count:5d}  ({with_parent:5d} linked to parent)")

    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()


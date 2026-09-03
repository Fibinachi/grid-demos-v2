"""
Boston Property Assessment — Match & Enrich
============================================
Fetches all religious exempt (LUC=970, 906) property records from
Boston's CKAN Data Portal, matches against GRID churches by
normalized address, and enriches records with parcel IDs and
assessment data (value, area, year built, etc.).

API: https://data.boston.gov/api/3/action/datastore_search
Resource: ee73430d-96c0-423e-ad21-c4cfb54c8961

Strategy:
  The CKAN property data has no lat/lon, so we match by normalized
  address (street number + street name + city). We also try owner
  name matching for unmatched records.
"""

import json
import os
import re
import sys
import time
import requests

CHUNK_SIZE = 500
CKAN_BASE = "https://data.boston.gov/api/3/action/datastore_search"
RESOURCE_ID = "ee73430d-96c0-423e-ad21-c4cfb54c8961"
SOURCE_NAME = "boston_property_assessment"
BATCH_SIZE = 100
CACHE_FILE = r"E:\grid\data\boston_property_records.json"


def fetch_all_luc(luc_codes):
    """Fetch ALL records matching given LUC codes via CKAN pagination."""
    records = []
    for luc in luc_codes:
        offset = 0
        while True:
            url = (f"{CKAN_BASE}?resource_id={RESOURCE_ID}"
                   f"&limit={BATCH_SIZE}&offset={offset}"
                   f"&filters={json.dumps({'LUC': str(luc)})}")
            resp = requests.get(url).json()
            if not resp.get("success"):
                print(f"  ERROR LUC={luc} offset={offset}: {resp.get('error', resp)}")
                break
            batch = resp["result"]["records"]
            if not batch:
                break
            records.extend(batch)
            offset += BATCH_SIZE
            print(f"  LUC={luc}: {len(records)} so far...", end='\r')
            time.sleep(0.25)
        print(f"  LUC={luc}: {len([r for r in records if r.get('LUC')==str(luc)])} total")
    return records


def normalize_street(name):
    """Normalize a street name for matching."""
    if not name:
        return ""
    n = name.strip().upper()
    n = re.sub(r'\bSTREET\b', 'ST', n)
    n = re.sub(r'\bAVENUE\b', 'AV', n)
    n = re.sub(r'\bROAD\b', 'RD', n)
    n = re.sub(r'\bDRIVE\b', 'DR', n)
    n = re.sub(r'\bLANE\b', 'LN', n)
    n = re.sub(r'\bBOULEVARD\b', 'BLVD', n)
    n = re.sub(r'\bPARKWAY\b', 'PKWY', n)
    n = re.sub(r'\bCOURT\b', 'CT', n)
    n = re.sub(r'\bPLACE\b', 'PL', n)
    n = re.sub(r'\bSQUARE\b', 'SQ', n)
    n = re.sub(r'\bTERRACE\b', 'TER', n)
    n = re.sub(r'\bHIGHWAY\b', 'HWY', n)
    n = re.sub(r'\bCIRCLE\b', 'CIR', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = re.sub(r'[^\w\s]', '', n)
    return n


def normalize_owner(name):
    """Normalize owner/church name for matching."""
    if not name:
        return ""
    n = name.strip().upper()
    n = re.sub(r'\s+(INC|CORP|CORPORATION|LLC|TRUST|TRUSTEES|NOMINEE|REVOCABLE|LIVING|ETAL|ET\s+AL)\b.*$', '', n)
    n = re.sub(r'\bC/O\s+.+$', '', n)
    n = re.sub(r'\b(THE|OF|A)\b', ' ', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = n.rstrip(',. ')
    return n


def build_addr_key(st_num, st_name, city):
    """Build normalized address key for matching."""
    if not st_name:
        return None
    num = str(st_num or '').strip()
    street = normalize_street(st_name)
    c = (city or '').strip().upper()
    return f"{num}|{street}|{c}"


BOSTON_NEIGHBORHOODS = [
    'BOSTON', 'ALLSTON', 'BRIGHTON', 'CHARLESTOWN', 'DORCHESTER',
    'EAST BOSTON', 'HYDE PARK', 'JAMAICA PLAIN', 'MATTAPAN',
    'READVILLE', 'ROSLINDALE', 'ROXBURY', 'ROXBURY CROSSING',
    'SOUTH BOSTON', 'WEST ROXBURY',
]
# Map all neighborhoods to canonical 'BOSTON' for cross-matching
BOSTON_CITIES = {n: 'BOSTON' for n in BOSTON_NEIGHBORHOODS}
# Also include the generic forms
BOSTON_CITIES['ROXBURY CROSSING'] = 'BOSTON'


def get_church_addresses(conn):
    """Get all churches in Boston neighborhoods with their addresses."""
    placeholders = ','.join('?' for _ in BOSTON_NEIGHBORHOODS)
    sql = f"""
        SELECT ch.id, ch.name, ch.faith, ch.city, ch.state,
               ch.latitude, ch.longitude, ch.address,
               cc.value as contact_address
        FROM churches ch
        LEFT JOIN church_contact_values cc 
            ON cc.church_id = ch.id 
            AND cc.contact_type IN ('address', 'street_address')
        WHERE UPPER(ch.city) IN ({placeholders}) AND ch.state = 'MA'
    """
    return conn.execute(sql, BOSTON_NEIGHBORHOODS).fetchall()


def match_churches(conn, property_records):
    """Match property records to GRID churches by address + owner name."""
    churches = get_church_addresses(conn)
    print(f"\nBoston area churches in DB: {len(churches)}")

    def canonical_city(c):
        """Map neighborhood name to BOSTON for cross-matching."""
        uc = (c or '').strip().upper()
        return BOSTON_CITIES.get(uc, uc)

    # --- Build church address index ---
    church_by_key = {}
    for c in churches:
        addr = c[7] or c[8] or ''
        addr_upper = addr.strip().upper()
        # Strip trailing city/state/zip if present (e.g. "1248 BLUE HILL AVE, MATTAPAN, MA 02126")
        addr_clean = re.sub(r',\s*[A-Z\s]+\s*,\s*[A-Z]{2}\s+\d{5}(-\d{4})?\s*$', '', addr_upper)
        addr_clean = re.sub(r',\s*[A-Z\s]+\s*,\s*[A-Z]{2}\s*$', '', addr_clean)
        addr_clean = re.sub(r',\s+BOSTON\s*$', '', addr_clean)

        m = re.match(r'^(\d+[A-Z]?)\s+(.+)$', addr_clean)
        if m:
            num, street = m.groups()
            # Index with original city
            key = build_addr_key(num, street, c[3])
            if key:
                church_by_key.setdefault(key, []).append((c, addr))
            # Index with canonical BOSTON city
            key2 = build_addr_key(num, street, canonical_city(c[3]))
            if key2 and key2 != key:
                church_by_key.setdefault(key2, []).append((c, addr))
            # Index by just street name (no number) with canonical city
            nn_key = build_addr_key('', street, canonical_city(c[3]))
            if nn_key:
                church_by_key.setdefault(nn_key, []).append((c, addr))

    # --- Build property address index ---
    prop_by_key = {}
    for p in property_records:
        pcity = p.get('CITY')
        # Index with original city
        key = build_addr_key(p.get('ST_NUM'), p.get('ST_NAME'), pcity)
        if key:
            prop_by_key.setdefault(key, []).append(p)
        # Index with canonical BOSTON city
        key2 = build_addr_key(p.get('ST_NUM'), p.get('ST_NAME'), canonical_city(pcity))
        if key2 and key2 != key:
            prop_by_key.setdefault(key2, []).append(p)
        # Index by just street name with canonical city
        if p.get('ST_NAME'):
            nn_key = build_addr_key('', p.get('ST_NAME'), canonical_city(pcity))
            if nn_key:
                prop_by_key.setdefault(nn_key, []).append(p)

    # --- Phase 1: Address matching ---
    matched = []
    matched_ids = set()
    for key, churches_list in church_by_key.items():
        if key in prop_by_key:
            for c, _ in churches_list:
                if c[0] not in matched_ids:
                    matched.append((c, prop_by_key[key]))
                    matched_ids.add(c[0])

    print(f"  Address-matched: {len(matched_ids)}")

    # --- Phase 2: Owner name matching for unmatched ---
    unmatched = [c for c in churches if c[0] not in matched_ids]

    owner_index = {}
    for p in property_records:
        on = normalize_owner(p.get('OWNER', ''))
        if on and len(on) > 4:
            owner_index.setdefault(on, []).append(p)

    name_matched = 0
    for c in unmatched:
        cn = normalize_owner(c[1])
        if cn and cn in owner_index:
            matched.append((c, owner_index[cn]))
            matched_ids.add(c[0])
            name_matched += 1

    print(f"  Name-matched: {name_matched}")
    print(f"  Total matched: {len(matched_ids)}")
    print(f"  Unmatched: {len(churches) - len(matched_ids)}")

    final_unmatched = [c for c in churches if c[0] not in matched_ids]
    return matched, final_unmatched


def ensure_columns(conn):
    """Add boston_* columns to churches table if missing."""
    cols = [c[1] for c in conn.execute('PRAGMA table_info(churches)').fetchall()]
    additions = []
    if 'boston_pid' not in cols:
        additions.append("ALTER TABLE churches ADD COLUMN boston_pid TEXT")
    if 'boston_property_json' not in cols:
        additions.append("ALTER TABLE churches ADD COLUMN boston_property_json TEXT")
    for sql in additions:
        print(f"  Adding column: {sql}")
        conn.execute(sql)
    if additions:
        conn.commit()
    return cols


def enrich_churches(conn, matched):
    """Add boston_pid column and store enrichment data on churches table."""
    ensure_columns(conn)

    hits = 0
    for ch, props in matched:
        church_id = ch[0]
        p = props[0]
        pid = p.get('PID') or ''

        assessment = {
            'pid': pid,
            'gross_area': p.get('GROSS_AREA'),
            'land_sf': p.get('LAND_SF'),
            'living_area': p.get('LIVING_AREA'),
            'land_value': p.get('LAND_VALUE'),
            'bldg_value': p.get('BLDG_VALUE'),
            'total_value': p.get('TOTAL_VALUE'),
            'gross_tax': p.get('GROSS_TAX'),
            'yr_built': p.get('YR_BUILT'),
            'yr_remodel': p.get('YR_REMODEL'),
            'overall_cond': p.get('OVERALL_COND'),
            'owner': p.get('OWNER'),
            'luc': p.get('LUC'),
            'lu_desc': p.get('LU_DESC'),
            'st_num': p.get('ST_NUM'),
            'st_name': p.get('ST_NAME'),
        }

        conn.execute(
            "UPDATE churches SET boston_pid = ?, boston_property_json = ? WHERE id = ?",
            (pid, json.dumps(assessment), church_id)
        )

        hits += 1
        if hits % 200 == 0:
            conn.commit()
            print(f"    Enriched {hits}/{len(matched)}...")

    conn.commit()
    return hits


def report_matches(matched, unmatched, property_records, churches_total):
    """Print detailed match/miss report."""
    matched_pids = set()
    for _, props in matched:
        for p in props:
            pid = p.get('PID')
            if pid:
                matched_pids.add(pid)

    unmatched_props = [p for p in property_records if p.get('PID') not in matched_pids]

    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"  Boston churches in DB:     {churches_total}")
    print(f"  Matched & enriched:        {len(matched)}")
    print(f"  Missed (unmatched):        {len(unmatched)}")
    print(f"  Property records fetched:  {len(property_records)}")
    print(f"  Properties with matches:   {len(matched_pids)}")
    print(f"  Unmatched properties:      {len(unmatched_props)}")

    print(f"\n{'='*70}")
    print(f"MISSED — Churches in DB with no property match ({len(unmatched)})")
    print(f"{'='*70}")
    for c in sorted(unmatched, key=lambda x: x[1])[:40]:
        addr = c[7] or c[8] or '(no address)'
        faith = c[2] or '?'
        print(f"  #{c[0]:>8} [{faith:20s}] {c[1][:60]}")
        print(f"          {c[3]},{c[4]}  addr={addr}  ({c[5] or '?'},{c[6] or '?'})")
    if len(unmatched) > 40:
        print(f"  ... and {len(unmatched) - 40} more")

    print(f"\n{'='*70}")
    print(f"UNMATCHED PROPERTIES — Not in our DB ({len(unmatched_props)})")
    print(f"{'='*70}")
    for p in sorted(unmatched_props, key=lambda x: x.get('OWNER', ''))[:30]:
        owner = p.get('OWNER', '')[:60]
        addr = f"{p.get('ST_NUM') or ''} {p.get('ST_NAME') or ''}"
        val = p.get('TOTAL_VALUE') or '?'
        area = p.get('GROSS_AREA') or '?'
        print(f"  PID={p.get('PID'):>12}  ${str(val):>12}  {str(area):>8}sf  {owner}")
        print(f"                    {addr}  [{p.get('LU_DESC')}]")
    if len(unmatched_props) > 30:
        print(f"  ... and {len(unmatched_props) - 30} more")


if __name__ == '__main__':
    print("=" * 70)
    print("Boston Property Assessment — Church Match & Enrich")
    print("=" * 70)

    # Step 1: Fetch or load cached property records
    cache_path = CACHE_FILE
    if os.path.exists(cache_path):
        print(f"\n[1/3] Loading cached property records ({cache_path})...")
        with open(cache_path) as f:
            property_records = json.load(f)
        print(f"  {len(property_records)} records loaded from cache")
    else:
        print("\n[1/3] Fetching religious exempt properties from CKAN...")
        property_records = fetch_all_luc([970, 906])
        print(f"  {len(property_records)} total religious exempt records fetched")
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(property_records, f, indent=2)
        print(f"  Cached to {cache_path}")

    # LU_DESC breakdown
    lu_counts = {}
    for p in property_records:
        desc = p.get('LU_DESC', 'UNKNOWN')
        lu_counts[desc] = lu_counts.get(desc, 0) + 1
    print("\n  LU code breakdown:")
    for desc, cnt in sorted(lu_counts.items(), key=lambda x: -x[1]):
        print(f"    {desc}: {cnt}")

    # Step 2: Connect to DB and match
    print("\n[2/3] Connecting to churches.db and matching...")
    sys.path.insert(0, r'E:\grid')
    from gw_db import connect
    conn = connect(r'E:\grid\churches.db')
    placeholders = ','.join('?' for _ in BOSTON_NEIGHBORHOODS)
    churches_total = conn.execute(
        f"SELECT COUNT(*) FROM churches WHERE UPPER(city) IN ({placeholders}) AND state = 'MA'",
        BOSTON_NEIGHBORHOODS
    ).fetchone()[0]

    matched, unmatched = match_churches(conn, property_records)

    # Step 3: Enrich
    print("\n[3/3] Enriching matched churches...")
    hits = enrich_churches(conn, matched)
    print(f"  Done! {hits} churches enriched with Boston property data.")

    # Report
    report_matches(matched, unmatched, property_records, churches_total)

    conn.close()

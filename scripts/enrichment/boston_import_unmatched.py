"""
Import unmatched Boston property records as new church entries.
Categorizes by type (church, synagogue, mosque, cemetery, hospital)
and by faith (Christian, Judaism, Islam).

Strategy:
  LUC=970  = "CHURCH, SYNAGOGUE" — physical religious buildings
  LUC=906  = "RELIGIOUS Organization" — religious orgs (admin, cemeteries, schools)

We classify by owner name keywords, then add to DB with boston_pid + assessment data.
"""

import json, re, sys, os
sys.path.insert(0, r'E:\grid')
from gw_db import connect

SOURCE = 'boston_property_assessment'
CACHE = r'E:\grid\data\boston_property_records.json'
PROVENANCE_SCRIPT = 'boston_import_unmatched.py'

# Multi-word patterns that are clearly Christian churches
CHRISTIAN_CHURCH_PATTERNS = [
    'BAPTIST', 'METHODIST', 'LUTHERAN', 'EPISCOPAL', 'PRESBYTERIAN',
    'PENTECOSTAL', 'APOSTOLIC', 'EVANGELICAL', 'CONGREGATIONAL',
    'CHURCH OF GOD', 'CHURCH OF CHRIST', 'CHURCH OF THE NAZARENE',
    'SEVENTH DAY', 'ADVENTIST', 'MISSIONARY BAPTIST',
    'UNITED PENTECOSTAL', 'PENT APSTL', 'CHURCH OF THE',
    'CATHOLIC', 'ROMAN CATH', 'ARCHDIOCES', 'ORTHODOX',
    'SALVATION ARMY', 'JEHOVAH', 'MOSQUE', 'ISLAMIC',
    'CHRISTIAN SCIENCE', 'UNITARIAN', 'UNIVERSALIST',
    'MORMON', 'LDS', 'REORG', 'CHURCH OF JESUS CHRIST',
]

# Jewish congregation patterns
JEWISH_PATTERNS = [
    'BNAI', 'JESHURUN', 'SYNAGOGUE', 'CONGREGATION KADIMAH',
    'DAUGHTERS OF ISRAEL', 'TEMPLE BETH', 'BETH ISRAEL',
    'JEWISH', 'HEBREW', 'SHALOM', 'CHABAD',
]

# Islamic patterns  
ISLAMIC_PATTERNS = [
    'MOSQUE', 'ISLAMIC', 'MUSLIM',
]


def classify(owner, luc, lu_desc):
    """Classify a property by faith and type."""
    o = (owner or '').upper().strip()
    d = (lu_desc or '').upper()
    name = f"{o} {d}"

    # --- CEMETERIES ---
    if any(w in name for w in ['CEMETERY', 'CEMETRY']):
        if any(w in name for w in ['JEWISH', 'JESHURUN', 'HEBREW', 'BNAI', 'ISRAEL', 'SHALOM']):
            return ('Judaism', None, 'cemetery')
        return ('Christian', 'Catholic', 'cemetery')

    # --- HOSPITALS ---
    if any(w in name for w in ['HOSPITAL', 'DEACONESS', 'MEDICAL CENTER']):
        if 'BETH ISRAEL' in name:
            return ('Judaism', None, 'hospital')
        return ('Christian', None, 'hospital')

    # --- LUC=970: Religious buildings ---
    if luc == '970':
        # Islamic
        for pat in ISLAMIC_PATTERNS:
            if pat in name:
                # Check if it's also got church words (like "ISLAMIC CHURCH")
                if 'CHURCH' in name and 'MOSQUE' not in name:
                    continue  # probably not Islamic
                return ('Islam', None, 'mosque')

        # Jewish
        for pat in JEWISH_PATTERNS:
            if pat in name:
                return ('Judaism', None, 'synagogue')

        # "TEMPLE" alone is tricky — many Christian churches use "TEMPLE"
        if 'TEMPLE' in name and not any(x in name for x in ['BAPTIST', 'CHURCH', 'CHRISTIAN', 'PENTECOSTAL', 'APOSTOLIC', 'GOD', 'CHRIST']):
            return ('Judaism', None, 'synagogue')

        # Christian — try denomination
        if 'BAPTIST' in name:
            return ('Christian', 'Baptist', 'church')
        if 'CATHOLIC' in name or 'ROMAN CATH' in name or 'ARCHDIOCES' in name:
            return ('Christian', 'Catholic', 'church')
        if 'METHODIST' in name:
            return ('Christian', 'Methodist', 'church')
        if 'LUTHERAN' in name:
            return ('Christian', 'Lutheran', 'church')
        if 'EPISCOPAL' in name:
            return ('Christian', 'Episcopal', 'church')
        if 'ORTHODOX' in name:
            return ('Christian', 'Orthodox', 'church')
        if 'PENTECOSTAL' in name or 'PENT APSTL' in name:
            return ('Christian', 'Pentecostal', 'church')
        if 'APOSTOLIC' in name:
            return ('Christian', 'Pentecostal/Apostolic', 'church')
        if 'EVANGELICAL' in name:
            return ('Christian', 'Evangelical', 'church')
        if 'CONGREGATIONAL' in name:
            return ('Christian', 'Congregational', 'church')
        if 'PRESBYTERIAN' in name:
            return ('Christian', 'Presbyterian', 'church')
        if 'CHURCH OF GOD' in name:
            return ('Christian', 'Church of God', 'church')
        if 'CHURCH OF CHRIST' in name:
            return ('Christian', 'Church of Christ', 'church')
        if 'NAZARENE' in name:
            return ('Christian', 'Nazarene', 'church')
        if 'SALVATION ARMY' in name:
            return ('Christian', 'Salvation Army', 'church')
        if 'JEHOVAH' in name:
            return ('Christian', "Jehovah's Witnesses", 'church')
        if 'CHRISTIAN' in name or 'CHURCH' in name:
            return ('Christian', None, 'church')
        if 'UNITARIAN' in name or 'UNIVERSALIST' in name:
            return ('Christian', 'Unitarian Universalist', 'church')

        # Default for LUC=970
        return ('Christian', None, 'church')

    # --- LUC=906: Religious Organizations ---
    if luc == '906':
        if any(w in name for w in ['MOSQUE', 'ISLAMIC', 'MUSLIM']):
            return ('Islam', None, 'mosque')
        for pat in JEWISH_PATTERNS:
            if pat in name:
                return ('Judaism', None, 'religious_org')

        # Religious organization types
        if 'CONVENT' in name or 'MONASTERY' in name or 'RECTORY' in name or 'PRIORY' in name:
            return ('Christian', 'Catholic', 'religious_house')
        if 'HOUSING' in name or 'APARTMENT' in name or 'HOMES' in name or 'SHELTER' in name:
            return ('Christian', None, 'housing')
        if 'SCHOOL' in name or 'ACADEMY' in name or 'EDUCATION' in name or 'YOUTH' in name or 'CAMP' in name:
            return ('Christian', None, 'school')
        if 'SOCIAL' in name or 'SERVICES' in name or 'CHARITIES' in name or 'COMMUNITY' in name:
            return ('Christian', None, 'community_center')

        # Default for LUC=906
        return ('Christian', None, 'religious_org')

    return ('Unknown', None, 'unknown')


def clean_name(owner_raw):
    """Clean up the owner name for use as a church name."""
    if not owner_raw:
        return 'Unknown'
    n = owner_raw.strip()
    # Remove common legal suffixes
    n = re.sub(r'\s+(INC|CORP|CORPORATION|LLC|TRUST|NOMINEE|REVOCABLE|LIVING|ETAL|ET\s+AL)\b.*$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\bC/O\s+.+$', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\b(THE|OF|A)\s+\b', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    n = n.rstrip(',. ')
    return n if n else owner_raw.strip()


def build_name(owner, faith, ptype):
    """Build a display name with type suffix where helpful."""
    name = clean_name(owner)
    if not name:
        name = f"Unknown {faith} {ptype}"
    return name


def main():
    print("=" * 70)
    print("Boston Property — Import Unmatched Records")
    print("=" * 70)

    # Load properties
    with open(CACHE) as f:
        all_props = json.load(f)

    # Get already-matched PIDs
    conn = connect(r'E:\grid\churches.db')
    matched_pids = set()
    for row in conn.execute("SELECT boston_pid FROM churches WHERE boston_pid IS NOT NULL").fetchall():
        if row[0]:
            matched_pids.add(row[0])

    # Also check what PIDs already exist as new entries from a previous run
    existing_pid_vals = set()
    for row in conn.execute(
        "SELECT value FROM church_contact_values WHERE contact_type = 'boston_pid'"
    ).fetchall():
        if row[0]:
            existing_pid_vals.add(row[0])

    unmatched = [p for p in all_props if p.get('PID') not in matched_pids and p.get('PID') not in existing_pid_vals]
    print(f"\nTotal property records: {len(all_props)}")
    print(f"Already matched: {len(matched_pids)}")
    print(f"Already imported as new: {len(existing_pid_vals - matched_pids) if existing_pid_vals else 0}")
    print(f"To import: {len(unmatched)}")

    # First check if our columns exist
    cols = [c[1] for c in conn.execute('PRAGMA table_info(churches)').fetchall()]
    if 'boston_pid' not in cols:
        conn.execute("ALTER TABLE churches ADD COLUMN boston_pid TEXT")
    if 'boston_property_json' not in cols:
        conn.execute("ALTER TABLE churches ADD COLUMN boston_property_json TEXT")
    conn.commit()

    # Classify and import
    by_faith = {}
    by_type = {}
    imported = 0
    skipped = 0

    for p in unmatched:
        owner = p.get('OWNER') or ''
        luc = p.get('LUC') or ''
        lu_desc = p.get('LU_DESC') or ''
        pid = p.get('PID') or ''

        faith, denomination, ptype = classify(owner, luc, lu_desc)

        # Skip unknown
        if faith == 'Unknown':
            skipped += 1
            continue

        # Build church name
        name = clean_name(owner)
        if not name:
            name = f"Unknown ({ptype})"

        # Build address
        addr_parts = []
        if p.get('ST_NUM'):
            addr_parts.append(str(p.get('ST_NUM')))
        if p.get('ST_NAME'):
            addr_parts.append(p.get('ST_NAME'))
        address = ' '.join(addr_parts) if addr_parts else None

        city = (p.get('CITY') or 'BOSTON').title()
        zip_code = (p.get('ZIP_CODE') or '').strip()

        # Build assessment JSON
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
            'owner': owner,
            'luc': luc,
            'lu_desc': lu_desc,
            'st_num': p.get('ST_NUM'),
            'st_name': p.get('ST_NAME'),
        }

        # Insert new church
        try:
            c = conn.execute("""
                INSERT INTO churches (
                    name, faith, city, state, zip, address,
                    boston_pid, boston_property_json,
                    landmark_type, source, denomination
                ) VALUES (?, ?, ?, 'MA', ?, ?, ?, ?, ?, ?, ?)
            """, (
                name, faith, city, zip_code, address,
                pid, json.dumps(assessment),
                ptype, SOURCE, denomination
            ))

            # Get new church_id from cursor
            church_id = c.lastrowid

            # Also store PID as contact value
            try:
                conn.execute(
                    "INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, is_primary) VALUES (?, 'boston_pid', ?, 1.0, ?, 1)",
                    (church_id, pid, SOURCE)
                )
            except Exception as e_pid:
                # The contact_type constraint might block this; skip gracefully
                pass

            by_faith[faith] = by_faith.get(faith, 0) + 1
            by_type[ptype] = by_type.get(ptype, 0) + 1
            imported += 1

            if imported % 100 == 0:
                conn.commit()
                print(f"  Imported {imported}...")

        except Exception as e:
            print(f"  ERROR importing PID={pid}: {e}")
            skipped += 1

    conn.commit()

    # Report
    print(f"\n{'='*70}")
    print(f"IMPORT RESULTS")
    print(f"{'='*70}")
    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")

    print(f"\n  By Faith:")
    for faith, cnt in sorted(by_faith.items(), key=lambda x: -x[1]):
        print(f"    {faith}: {cnt}")

    print(f"\n  By Type:")
    for ptype, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {ptype}: {cnt}")

    conn.close()
    print(f"\nDone! {imported} new church records created.")


if __name__ == '__main__':
    main()

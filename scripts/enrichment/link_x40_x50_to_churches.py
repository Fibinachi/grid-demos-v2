"""
link_x40_x50_to_churches.py

Match X40 (food pantry) and X50 (school) NTEE-coded records to their parent churches
using a multi-phase matching strategy:

Phase 1: Exact address match (same street address, city, state, different ID)
Phase 2: Name overlap match (same city/state, one name contains the other)
Phase 3: PSS school → church matching by address
Phase 4: PSS school → church matching by name + city

Usage:
    python scripts/enrichment/link_x40_x50_to_churches.py [--dry-run] [--phase 1|2|3|4]
"""

import sqlite3
import sys
import re
import argparse

DB_PATH = 'churches.db'


def normalize(s):
    """Normalize a string for comparison."""
    if not s:
        return ''
    s = s.upper()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Remove common suffixes
    for suffix in [' INC', ' CORP', ' CORPORATION', ' LLC', ' LTD', ' THE']:
        if s.endswith(suffix) and len(s) > len(suffix) + 2:
            s = s[:-len(suffix)]
    return s.strip()


def clean_name(name):
    """Clean a name for matching."""
    if not name:
        return ''
    name = name.upper()
    # Remove common suffixes
    name = re.sub(r'\b(INC|CORP|CORPORATION|LLC|LTD|THE|NPO|ORG|FOUNDATION)\b\.?\s*', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def get_church_keywords(name):
    """Extract significant keywords from a church name for matching."""
    if not name:
        return []
    n = normalize(name)
    words = n.split()
    # Filter out very common words
    stopwords = {'THE', 'A', 'AN', 'OF', 'IN', 'AND', 'AT', 'TO', 'FOR', 'INC',
                 'CHURCH', 'TEMPLE', 'MINISTRY', 'MINISTRIES', 'CENTER', 'CENTRE',
                 'FELLOWSHIP', 'MISSION', 'OUTREACH', 'INTERNATIONAL', 'WORLD',
                 'GLOBAL', 'AMERICAN', 'UNITED', 'NORTH', 'SOUTH', 'EAST', 'WEST',
                 'ST', 'SAINT', 'MT', 'MOUNT', 'CHRISTIAN', 'BAPTIST', 'METHODIST',
                 'CATHOLIC', 'LUTHERAN', 'PRESBYTERIAN', 'EPISCOPAL', 'PENTECOSTAL',
                 'COMMUNITY', 'BIBLE', 'GOSPEL', 'GRACE', 'FAITH', 'HOPE', 'LOVE',
                 'LIFE', 'LIVING', 'NEW', 'OLD', 'FIRST', 'SECOND', 'THIRD'}
    significant = [w for w in words if w not in stopwords and len(w) > 2]
    return significant


def log_match(cursor, x_id, x_type, x_name, church_id, church_name, method, confidence):
    """Record a match in the provenance_log table."""
    try:
        cursor.execute("""
            INSERT INTO provenance_log (source_table, source_id, target_table, target_id,
                                        match_type, confidence, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('churches', x_id, 'churches', church_id,
              f'parent_church_{x_type}', confidence,
              f'Matched by {method}: "{x_name}" → "{church_name}"'))
    except Exception:
        pass  # Table might not exist or have different schema


def phase1_address_match(db, dry_run=False):
    """Phase 1: Match by exact address (same street, city, state, different ID)."""
    cur = db.cursor()
    print(f"\n{'='*60}")
    print(f"PHASE 1: Address-based matching")
    print(f"{'='*60}")

    # Create temp table of church addresses
    cur.execute("DROP TABLE IF EXISTS temp_church_addrs")
    cur.execute("""
        CREATE TEMP TABLE temp_church_addrs AS
        SELECT id, TRIM(address) as addr, TRIM(city) as cty, TRIM(state) as st
        FROM churches
        WHERE org_type IN ('church', 'parish')
          AND address != '' AND address IS NOT NULL
          AND city != '' AND city IS NOT NULL
          AND state != '' AND state IS NOT NULL
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tca ON temp_church_addrs(addr, cty, st)")
    church_count = cur.execute("SELECT COUNT(*) FROM temp_church_addrs").fetchone()[0]
    print(f"  Church addresses indexed: {church_count:,}")

    # Find X40/X50 at same address as a church (excluding self-matches)
    cur.execute("""
        SELECT x.id, x.name, x.address, x.city, x.state, x.ntee_code,
               c.id, c.name,
               CASE WHEN x.ntee_code LIKE 'X40%' THEN 'food_pantry' ELSE 'school' END as type_label
        FROM churches x
        JOIN temp_church_addrs t ON TRIM(x.address) = t.addr
            AND TRIM(x.city) = t.cty AND TRIM(x.state) = t.st
        JOIN churches c ON c.id = t.id
        WHERE (x.ntee_code LIKE 'X40%' OR x.ntee_code LIKE 'X50%')
          AND x.id != c.id
          AND x.parent_church_id IS NULL
          AND x.address != '' AND x.address IS NOT NULL
        ORDER BY type_label, x.state, x.city
    """)

    matches = cur.fetchall()
    print(f"  Address matches found: {len(matches)}")
    for m in matches:
        print(f"    {m[8]}: ID={m[0]} \"{str(m[1])[:45]}\"")
        print(f"      @ {str(m[2])[:35]}, {m[3]}, {m[4]} ({m[5]})")
        print(f"      → Church ID={m[6]} \"{str(m[7])[:45]}\"")

    if dry_run:
        print(f"\n  [DRY RUN] Would set parent_church_id on {len(matches)} records")
        return

    updated = 0
    for m in matches:
        x_id, church_id, type_label = m[0], m[6], m[8]
        try:
            cur.execute("UPDATE churches SET parent_church_id = ? WHERE id = ?",
                        (church_id, x_id))
            log_match(cur, x_id, type_label, m[1], church_id, m[7], 'address_exact', 0.95)
            updated += 1
        except Exception as e:
            print(f"    ERROR updating ID={x_id}: {e}")

    db.commit()
    print(f"  Updated: {updated} records")
    return updated


def normalize_address(addr):
    """Normalize an address for fuzzy matching."""
    if not addr:
        return ''
    a = addr.upper().strip()
    # Normalize street suffixes
    replacements = {
        ' STREET': ' ST', ' AVENUE': ' AVE', ' ROAD': ' RD',
        ' DRIVE': ' DR', ' LANE': ' LN', ' BOULEVARD': ' BLVD',
        ' PARKWAY': ' PKWY', ' COURT': ' CT', ' PLACE': ' PL',
        ' CIRCLE': ' CIR', ' HIGHWAY': ' HWY', ' TRAIL': ' TRL',
        ' SUITE': ' STE', ' APARTMENT': ' APT', ' FLOOR': ' FL',
        ' ROOM': ' RM', ' BUILDING': ' BLDG', ' BOX': ' PO BOX',
        ' PO BOX': ' POBOX', 'P O BOX': ' POBOX', 'P.O. BOX': ' POBOX',
        ' NORTH ': ' N ', ' SOUTH ': ' S ', ' EAST ': ' E ', ' WEST ': ' W ',
        ' NORTHEAST ': ' NE ', ' NORTHWEST ': ' NW ',
        ' SOUTHEAST ': ' SE ', ' SOUTHWEST ': ' SW ',
    }
    for old, new in replacements.items():
        a = a.replace(old, new)
    # Remove all punctuation
    a = re.sub(r'[^\w\s]', ' ', a)
    a = re.sub(r'\s+', ' ', a).strip()
    # Remove unit numbers for better matching (STE 100, APT 2B, #4, etc)
    a = re.sub(r'\b(STE|APT|UNIT|SUITE|RM|ROOM|FL|FLOOR|#)\s*\d+\w*\b', '', a)
    a = re.sub(r'\s+', ' ', a).strip()
    return a


def phase2_normalized_address_match(db, dry_run=False):
    """Phase 2: Match by normalized address (handles St vs Street, etc)."""
    cur = db.cursor()
    print(f"\n{'='*60}")
    print(f"PHASE 2: Normalized address matching")
    print(f"{'='*60}")

    # Build temp table with normalized addresses
    cur.execute("DROP TABLE IF EXISTS temp_church_norm")
    cur.execute("""
        CREATE TEMP TABLE temp_church_norm AS
        SELECT id, TRIM(address) as addr, TRIM(city) as cty, TRIM(state) as st
        FROM churches
        WHERE org_type IN ('church', 'parish')
          AND address != '' AND address IS NOT NULL
          AND city != '' AND city IS NOT NULL
          AND state != '' AND state IS NOT NULL
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tcn ON temp_church_norm(addr, cty, st)")

    # Get X40/X50 records without parent
    cur.execute("""
        SELECT x.id, x.name, x.address, x.city, x.state, x.ntee_code,
               CASE WHEN x.ntee_code LIKE 'X40%' THEN 'food_pantry' ELSE 'school' END as type_label
        FROM churches x
        JOIN temp_church_norm t ON TRIM(x.address) = t.addr
            AND TRIM(x.city) = t.cty AND TRIM(x.state) = t.st
        JOIN churches c ON c.id = t.id
        WHERE (x.ntee_code LIKE 'X40%' OR x.ntee_code LIKE 'X50%')
          AND x.id != c.id
          AND x.parent_church_id IS NULL
          AND x.address != '' AND x.address IS NOT NULL
        GROUP BY x.id
    """)
    already_matched = set(r[0] for r in cur.fetchall())
    print(f"  Already matched by exact address: {len(already_matched)}")

    # Build normalized address index in Python
    cur.execute("""
        SELECT id, address, city, state
        FROM churches
        WHERE org_type IN ('church', 'parish')
          AND address != '' AND address IS NOT NULL
          AND city != '' AND city IS NOT NULL
          AND state != '' AND state IS NOT NULL
    """)
    church_norm = {}
    for row in cur.fetchall():
        cid, caddr, ccity, cstate = row
        nor_addr = normalize_address(caddr)
        nor_city = ccity.upper().strip()
        nor_st = cstate.upper().strip()
        key = (nor_addr, nor_city, nor_st)
        if key not in church_norm:
            church_norm[key] = []
        church_norm[key].append(cid)
    print(f"  Normalized church addresses indexed: {len(church_norm):,}")

    # Get church names lookup
    cur.execute("SELECT id, name FROM churches")
    church_names = {r[0]: r[1] for r in cur.fetchall()}

    matches = []
    cur.execute("""
        SELECT x.id, x.name, x.address, x.city, x.state, x.ntee_code
        FROM churches x
        WHERE (x.ntee_code LIKE 'X40%' OR x.ntee_code LIKE 'X50%')
          AND x.parent_church_id IS NULL
          AND x.address != '' AND x.address IS NOT NULL
        ORDER BY x.id
    """)

    for row in cur.fetchall():
        x_id, x_name, x_addr, x_city, x_state, x_ntee = row
        if x_id in already_matched:
            continue

        nor_addr = normalize_address(x_addr)
        nor_city = x_city.upper().strip() if x_city else ''
        nor_st = x_state.upper().strip() if x_state else ''
        if not nor_addr or not nor_city or not nor_st:
            continue

        key = (nor_addr, nor_city, nor_st)
        church_ids = church_norm.get(key, [])
        for cid in church_ids:
            if cid != x_id:
                type_label = 'food_pantry' if x_ntee.startswith('X40') else 'school'
                matches.append((x_id, x_name, cid, church_names.get(cid, '?'), type_label, 'normalized_address'))
                break  # Take first match

    print(f"  Additional normalized address matches: {len(matches)}")
    for m in matches:
        print(f"    {m[4]}: ID={m[0]} \"{str(m[1])[:45]}\"")
        print(f"      → Church ID={m[2]} \"{str(m[3])[:45]}\"")

    if dry_run:
        return

    updated = 0
    for m in matches:
        try:
            cur.execute("UPDATE churches SET parent_church_id = ? WHERE id = ? AND parent_church_id IS NULL",
                        (m[2], m[0]))
            if cur.rowcount > 0:
                log_match(cur, m[0], m[4], m[1], m[2], m[3], 'normalized_address', 0.9)
                updated += 1
        except Exception as e:
            print(f"    ERROR: {e}")

    db.commit()
    print(f"  Updated: {updated} records")
    return updated

    print(f"  Name matches found: {len(matches)}")
    shown = set()
    for m in matches:
        key = (m[0], m[2])
        if key not in shown:
            print(f"    {m[4]}: ID={m[0]} \"{str(m[1])[:45]}\"")
            print(f"      → Church ID={m[2]} \"{str(m[3])[:45]}\" ({m[5]})")
            shown.add(key)

    if dry_run:
        print(f"\n  [DRY RUN] Would set parent_church_id on {len(matches)} records")
        return

    updated = 0
    seen = set()
    for m in matches:
        x_id, church_id, method = m[0], m[2], m[5]
        key = (x_id, church_id)
        if key in seen:
            continue
        seen.add(key)
        try:
            cur.execute("UPDATE churches SET parent_church_id = ? WHERE id = ? AND parent_church_id IS NULL",
                        (church_id, x_id))
            if cur.rowcount > 0:
                log_match(cur, x_id, m[4], m[1], church_id, m[3], method, 0.85)
                updated += 1
        except Exception as e:
            print(f"    ERROR updating ID={x_id}: {e}")

    db.commit()
    print(f"  Updated: {updated} records")
    return updated


def phase3_pss_address_match(db, dry_run=False):
    """Phase 3: Match PSS schools to churches by address."""
    cur = db.cursor()
    print(f"\n{'='*60}")
    print(f"PHASE 3: PSS School → Church address matching")
    print(f"{'='*60}")

    # Only match religious PSS schools
    cur.execute("""
        SELECT p.id, p.pinst, p.paddrs, p.pcity, p.pstabb
        FROM pss_schools p
        WHERE p.relig_label IN ('Catholic', 'Other religious')
          AND p.merge_target_id IS NULL
          AND p.paddrs != '' AND p.paddrs IS NOT NULL
    """)
    pss_schools = cur.fetchall()
    print(f"  Religious PSS schools with address: {len(pss_schools):,}")

    # Create temp table of church addresses
    cur.execute("DROP TABLE IF EXISTS temp_church_addrs2")
    cur.execute("""
        CREATE TEMP TABLE temp_church_addrs2 AS
        SELECT id, TRIM(address) as addr, TRIM(city) as cty, TRIM(state) as st
        FROM churches
        WHERE org_type IN ('church', 'parish')
          AND address != '' AND address IS NOT NULL
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tca2 ON temp_church_addrs2(addr, cty, st)")

    # Match PSS schools to churches at same address
    cur.execute("""
        SELECT p.id, p.pinst, p.paddrs, p.pcity, p.pstabb,
               c.id, c.name
        FROM pss_schools p
        JOIN temp_church_addrs2 t ON TRIM(p.paddrs) = t.addr
            AND TRIM(p.pcity) = t.cty AND TRIM(p.pstabb) = t.st
        JOIN churches c ON c.id = t.id
        WHERE p.relig_label IN ('Catholic', 'Other religious')
          AND p.merge_target_id IS NULL
          AND p.paddrs != ''
    """)
    matches = cur.fetchall()
    print(f"  Address matches: {len(matches)}")
    for m in matches[:15]:
        print(f"    PSS ID={m[0]} \"{str(m[1])[:45]}\"")
        print(f"      @ {str(m[2])[:35]}, {m[3]}, {m[4]}")
        print(f"      → Church ID={m[5]} \"{str(m[6])[:45]}\"")

    if dry_run:
        print(f"\n  [DRY RUN] Would update {len(matches)} PSS records")
        return

    # Update pss_schools.merge_target_id
    updated = 0
    for m in matches:
        try:
            cur.execute("UPDATE pss_schools SET merge_target_id = ? WHERE id = ? AND merge_target_id IS NULL",
                        (m[5], m[0]))
            if cur.rowcount > 0:
                updated += 1
                # Also update the church's has_school flag
                cur.execute("UPDATE churches SET has_school = 'pss_matched' WHERE id = ? AND (has_school = '' OR has_school IS NULL)",
                            (m[5],))
        except Exception as e:
            print(f"    ERROR: {e}")

    db.commit()
    print(f"  Updated: {updated} PSS records")
    return updated


def phase4_pss_name_match(db, dry_run=False):
    """Phase 4: Match PSS schools to churches by name + city."""
    cur = db.cursor()
    print(f"\n{'='*60}")
    print(f"PHASE 4: PSS School → Church name matching")
    print(f"{'='*60}")

    # Get unmatched religious PSS schools
    cur.execute("""
        SELECT id, pinst, pcity, pstabb
        FROM pss_schools
        WHERE relig_label IN ('Catholic', 'Other religious')
          AND merge_target_id IS NULL
    """)
    schools = cur.fetchall()
    print(f"  Unmatched religious PSS schools: {len(schools):,}")

    # Get churches grouped by city/state
    cur.execute("""
        SELECT id, name, city, state
        FROM churches
        WHERE org_type IN ('church', 'parish')
    """)
    churches = cur.fetchall()
    church_by_loc = {}
    for c in churches:
        key = ((c[2] or '').strip().upper(), (c[3] or '').strip().upper())
        if key not in church_by_loc:
            church_by_loc[key] = []
        church_by_loc[key].append((c[0], c[1]))

    matches = []
    for sid, sname, scity, sstate in schools:
        if not sname or not scity:
            continue
        s_norm = normalize(sname)
        s_clean = clean_name(sname)

        # Catholic-specific matching: "ST X CATHOLIC SCHOOL" → "ST X CHURCH" or "ST X CATHOLIC CHURCH"
        is_catholic = False
        if 'CATHOLIC' in s_norm:
            is_catholic = True
            # Try to strip "CATHOLIC SCHOOL" to find base
            base = s_norm.replace('CATHOLIC SCHOOL', '').replace('CATHOLIC', '').strip()
        else:
            base = s_norm.replace('SCHOOL', '').replace('ACADEMY', '').replace('PRESCHOOL', '').replace('ELEMENTARY', '').strip()

        key = (scity.upper().strip(), sstate.upper().strip())
        local_churches = church_by_loc.get(key, [])

        for cid, cname in local_churches:
            if not cname:
                continue
            c_norm = normalize(cname)
            c_clean = clean_name(cname)

            # Check if school name (without school words) is contained in church name
            if len(base) > 5 and base in c_norm:
                matches.append((sid, sname, cid, cname, is_catholic))
                continue

            # Or church name is contained in school name
            if len(c_norm) > 5 and c_norm in s_norm:
                matches.append((sid, sname, cid, cname, is_catholic))
                continue

    print(f"  Name matches: {len(matches)}")
    for m in matches[:20]:
        print(f"    PSS ID={m[0]} \"{str(m[1])[:45]}\"")
        print(f"      → Church ID={m[2]} \"{str(m[3])[:45]}\" {'[CATHOLIC]' if m[4] else ''}")

    if dry_run:
        print(f"\n  [DRY RUN] Would update {len(matches)} PSS records")
        return

    updated = 0
    seen = set()
    for m in matches:
        key = (m[0], m[2])
        if key in seen:
            continue
        seen.add(key)
        try:
            cur.execute("UPDATE pss_schools SET merge_target_id = ? WHERE id = ? AND merge_target_id IS NULL",
                        (m[2], m[0]))
            if cur.rowcount > 0:
                updated += 1
                cur.execute("UPDATE churches SET has_school = 'pss_matched' WHERE id = ? AND (has_school = '' OR has_school IS NULL)",
                            (m[2],))
        except Exception as e:
            print(f"    ERROR: {e}")

    db.commit()
    print(f"  Updated: {updated} PSS records")
    return updated


def main():
    parser = argparse.ArgumentParser(description='Link X40/X50 records to parent churches')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no changes')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3, 4],
                        help='Run only a specific phase')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")

    print(f"Linking X40 (food pantry) and X50 (school) records to parent churches")
    print(f"Mode: {'DRY RUN (no changes)' if args.dry_run else 'LIVE UPDATE'}")

    total = 0

    if not args.phase or args.phase == 1:
        total += (phase1_address_match(db, args.dry_run) or 0)
    if not args.phase or args.phase == 2:
        total += (phase2_normalized_address_match(db, args.dry_run) or 0)
    if not args.phase or args.phase == 3:
        total += (phase3_pss_address_match(db, args.dry_run) or 0)
    if not args.phase or args.phase == 4:
        total += (phase4_pss_name_match(db, args.dry_run) or 0)

    print(f"\n{'='*60}")
    print(f"Total links created: {total}")

    # Summary
    if not args.dry_run:
        cur = db.cursor()
        x40_linked = cur.execute(
            "SELECT COUNT(*) FROM churches WHERE ntee_code LIKE 'X40%' AND parent_church_id IS NOT NULL"
        ).fetchone()[0]
        x50_linked = cur.execute(
            "SELECT COUNT(*) FROM churches WHERE ntee_code LIKE 'X50%' AND parent_church_id IS NOT NULL"
        ).fetchone()[0]
        pss_linked = cur.execute(
            "SELECT COUNT(*) FROM pss_schools WHERE merge_target_id IS NOT NULL"
        ).fetchone()[0]

        print(f"X40 (food pantry) linked: {x40_linked}")
        print(f"X50 (school) linked: {x50_linked}")
        print(f"PSS schools linked: {pss_linked}")

    db.close()


if __name__ == '__main__':
    main()

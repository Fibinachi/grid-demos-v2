"""
Restructure Chabad and Moravian hierarchies for proper intermediate linking.

For Chabad:
  HQ (Brooklyn)
    ├── Chabad on Campus International → campus_chabad entries
    ├── Regional organizations (Merkos, Rabbinic Org, etc.) → as-is
    └── chabad_house entries → directly under HQ (flat structure matches reality)

For Moravian:
  Province HQ → regional boards/districts → congregations by geography

  Northern Province (Bethlehem, PA)
    ├── Provincial Boards (Pension Fund, Women's Board)
    └── US congregations in: PA, NY, OH, MN, WI, MI, IL, IN, KY, AK, ND, etc.
  
  Southern Province (Winston-Salem, NC)
    ├── Provincial Boards (Women's Board Southern, etc.)
    └── US congregations in: NC, SC, GA, FL, VA, TN, TX, etc.

  Canadian District (Calgary)
    └── CA congregations

  Jamaica Province
    └── JM congregations

Usage:
    python scripts/db_maintenance/restructure_chabad_moravian_hierarchy.py
    python scripts/db_maintenance/restructure_chabad_moravian_hierarchy.py --dry-run
"""
import sqlite3, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

# ========================
# CHABAD RESTRUCTURING
# ========================

def restructure_chabad():
    print("\n" + "=" * 60)
    print("CHABAD RESTRUCTURING")
    print("=" * 60)
    
    # Step 1: Find HQ hierarchy ID
    hq_hid = c.execute(
        "SELECT id FROM chabad_hierarchy WHERE church_id = 270192"
    ).fetchone()
    if not hq_hid:
        print("  ERROR: Chabad HQ not found!")
        return
    hq_id = hq_hid[0]
    print(f"  HQ hierarchy id: {hq_id} (church #270192)")
    
    # Step 2: Find Chabad on Campus International hierarchy IDs
    campus_intl = c.execute("""
        SELECT id, church_id, name FROM chabad_hierarchy
        WHERE church_id IN (20513, 358955)
        ORDER BY id
    """).fetchall()
    campus_intl_id = campus_intl[0][0] if campus_intl else None
    print(f"  Chabad on Campus International hierarchy id: {campus_intl_id}")
    
    # Step 3: Relink campus_chabad entries to Chabad on Campus International
    if campus_intl_id:
        campus_entries = c.execute("""
            SELECT id, church_id, name, city, country
            FROM chabad_hierarchy
            WHERE chabad_type = 'campus_chabad'
              AND (parent_id != ? OR parent_id IS NULL)
              AND id NOT IN (?, ?)
            ORDER BY id
        """, (campus_intl_id, campus_intl[0][0], campus_intl[1][0] if len(campus_intl) > 1 else -1)).fetchall()
        
        print(f"  Relinking {len(campus_entries)} campus entries to Chabad on Campus International...")
        
        linked = 0
        if not dry_run:
            for hid, cid, name, city, country in campus_entries:
                c.execute("""
                    UPDATE chabad_hierarchy
                    SET parent_id = ?, parent_chabad_type = 'regional_office', relationship = 'affiliated_with'
                    WHERE id = ?
                """, (campus_intl_id, hid))
                linked += 1
                if linked % CHUNK == 0:
                    db.commit()
                    print(f"    Linked {linked}...")
        else:
            linked = len(campus_entries)
        
        print(f"  ✓ {linked} campus entries linked to Chabad on Campus International")
    
    # Step 4: Verify all non-HQ entries still have a parent
    orphan_count = c.execute("""
        SELECT COUNT(*) FROM chabad_hierarchy
        WHERE church_id != 270192 AND parent_id IS NULL
    """).fetchone()[0]
    print(f"  Orphans remaining: {orphan_count}")
    
    # Step 5: Fix any remaining orphans by linking to HQ
    if orphan_count > 0:
        print(f"  Fixing {orphan_count} orphans...")
        if not dry_run:
            fixed = 0
            orphans = c.execute("""
                SELECT id, chabad_type FROM chabad_hierarchy
                WHERE church_id != 270192 AND parent_id IS NULL
            """).fetchall()
            for hid, ctype in orphans:
                c.execute("""
                    UPDATE chabad_hierarchy
                    SET parent_id = ?, parent_chabad_type = 'hq', relationship = 'affiliated_with'
                    WHERE id = ?
                """, (hq_id, hid))
                fixed += 1
            db.commit()
            print(f"  ✓ Fixed {fixed} orphans")


# ========================
# MORAVIAN RESTRUCTURING  
# ========================

# Northern Province states
NORTHERN_STATES = {
    'PA', 'Pennsylvania', 'NY', 'New York', 'OH', 'Ohio',
    'MN', 'Minnesota', 'WI', 'Wisconsin',
    'MI', 'Michigan', 'IL', 'Illinois', 'IN', 'Indiana',
    'KY', 'Kentucky', 'AK', 'Alaska', 'ND', 'North Dakota',
    'CT', 'Connecticut', 'IA', 'Iowa', 'KS', 'Kansas',
    'MD', 'Maryland', 'MO', 'Missouri', 'NJ', 'New Jersey',
    'DC', 'WA', 'Washington', 'OR', 'Oregon',
    'CA', 'California', 'CO', 'Colorado',
    'MA', 'Massachusetts', 'NH', 'New Hampshire',
    'RI', 'Rhode Island', 'VT', 'Vermont', 'ME', 'Maine',
    'MT', 'Montana', 'WY', 'Wyoming', 'ID', 'Idaho',
    'NE', 'Nebraska', 'SD', 'South Dakota', 'UT', 'Utah',
    'NV', 'Nevada', 'AZ', 'Arizona', 'NM', 'New Mexico',
    'HI', 'Hawaii',
}

# Southern Province states
SOUTHERN_STATES = {
    'NC', 'North Carolina', 'SC', 'South Carolina',
    'GA', 'Georgia', 'FL', 'Florida', 'VA', 'Virginia',
    'TN', 'Tennessee', 'TX', 'Texas', 'AL', 'Alabama',
    'MS', 'Mississippi', 'AR', 'Arkansas', 'LA', 'Louisiana',
    'WV', 'West Virginia', 'DE', 'Delaware',
    'OK', 'Oklahoma',
}

def get_state_key(state):
    """Normalize state to canonical form."""
    if not state:
        return None
    s = state.strip()
    # Full name to abbreviation
    mapping = {
        'Pennsylvania': 'PA', 'New York': 'NY', 'Ohio': 'OH',
        'Minnesota': 'MN', 'Wisconsin': 'WI', 'Michigan': 'MI',
        'Illinois': 'IL', 'Indiana': 'IN', 'Kentucky': 'KY',
        'Alaska': 'AK', 'North Dakota': 'ND', 'Connecticut': 'CT',
        'Iowa': 'IA', 'Kansas': 'KS', 'Maryland': 'MD',
        'Missouri': 'MO', 'New Jersey': 'NJ',
        'Washington': 'WA', 'Oregon': 'OR', 'California': 'CA',
        'Colorado': 'CO', 'Massachusetts': 'MA',
        'North Carolina': 'NC', 'South Carolina': 'SC',
        'Georgia': 'GA', 'Florida': 'FL', 'Virginia': 'VA',
        'Tennessee': 'TN', 'Texas': 'TX', 'Alabama': 'AL',
        'Mississippi': 'MS', 'Arkansas': 'AR', 'Louisiana': 'LA',
        'West Virginia': 'WV', 'Delaware': 'DE', 'Oklahoma': 'OK',
        'Vermont': 'VT', 'New Hampshire': 'NH', 'Maine': 'ME',
        'Rhode Island': 'RI', 'Montana': 'MT', 'Wyoming': 'WY',
        'Idaho': 'ID', 'Nebraska': 'NE', 'South Dakota': 'SD',
        'Utah': 'UT', 'Nevada': 'NV', 'New Mexico': 'NM',
        'Arizona': 'AZ', 'Hawaii': 'HI',
    }
    return mapping.get(s, s)


def restructure_moravian():
    global hq_ids
    print("\n" + "=" * 60)
    print("MORAVIAN RESTRUCTURING")
    print("=" * 60)
    
    # Find hierarchy IDs for province HQs
    northern_id = c.execute(
        "SELECT id FROM moravian_hierarchy WHERE church_id = 5040297"
    ).fetchone()
    southern_id = c.execute(
        "SELECT id FROM moravian_hierarchy WHERE church_id = 4994208"
    ).fetchone()
    canadian_id = c.execute(
        "SELECT id FROM moravian_hierarchy WHERE church_id = 2298546"
    ).fetchone()
    jamaica_id = c.execute(
        "SELECT id FROM moravian_hierarchy WHERE church_id = 3294465"
    ).fetchone()
    
    hq_ids.update({
        'northern': northern_id[0] if northern_id else None,
        'southern': southern_id[0] if southern_id else None,
        'canadian': canadian_id[0] if canadian_id else None,
        'jamaica': jamaica_id[0] if jamaica_id else None,
    })
    print(f"  Northern Province HQ: id={hq_ids['northern']}")
    print(f"  Southern Province HQ: id={hq_ids['southern']}")
    print(f"  Canadian District:    id={hq_ids['canadian']}")
    print(f"  Jamaica Province:     id={hq_ids['jamaica']}")
    
    if not hq_ids['northern'] or not hq_ids['southern']:
        print("  ERROR: Northern or Southern Province HQ not found!")
        return
    
    # Step 1: First, clear all existing parent links for regular entries
    if not dry_run:
        c.execute("""
            UPDATE moravian_hierarchy
            SET parent_id = NULL, parent_moravian_type = NULL, relationship = NULL
            WHERE moravian_type NOT IN ('province_hq')
        """)
        db.commit()
        print("  Cleared all existing parent links")
    
    # Step 2: Unlink Western Cape (South Africa) from Northern Province
    # (This happened because 'Western Cape' was treated as a US state)
    if not dry_run:
        c.execute("""
            UPDATE moravian_hierarchy
            SET parent_id = NULL, parent_moravian_type = NULL, relationship = NULL
            WHERE country = 'ZA'
        """)
        db.commit()
        print("  Unlinked South African entries (were incorrectly under Northern Province)")
    
    # Step 3: Link US entries by state
    # Get all US non-province_hq entries
    us_entries = c.execute("""
        SELECT h.id, h.church_id, h.name, h.state, h.city, h.moravian_type
        FROM moravian_hierarchy h
        WHERE h.country = 'US'
          AND h.moravian_type != 'province_hq'
        ORDER BY h.id
    """).fetchall()
    
    linked_northern = 0
    linked_southern = 0
    unlinked = []
    
    for hid, cid, name, state, city, mtype in us_entries:
        state_key = get_state_key(state)
        
        if state_key in NORTHERN_STATES:
            target_id = hq_ids['northern']
            target_type = 'province_hq'
            linked_northern += 1
        elif state_key in SOUTHERN_STATES:
            target_id = hq_ids['southern']
            target_type = 'province_hq'
            linked_southern += 1
        else:
            unlinked.append((hid, name, state, city))
            continue
        
        if not dry_run:
            c.execute("""
                UPDATE moravian_hierarchy
                SET parent_id = ?, parent_moravian_type = ?, relationship = 'administered_by'
                WHERE id = ?
            """, (target_id, target_type, hid))
    
    if not dry_run:
        db.commit()
    
    print(f"\n  US linking results:")
    print(f"    Northern Province: {linked_northern}")
    print(f"    Southern Province: {linked_southern}")
    
    if unlinked:
        print(f"\n  Unlinked US entries ({len(unlinked)}):")
        for hid, name, state, city in unlinked[:10]:
            print(f"    #{hid} {name[:50]} | {city}, {state}")
        if len(unlinked) > 10:
            print(f"    ... and {len(unlinked) - 10} more")
    
    # Step 4: Link Canadian entries to Canadian District
    if hq_ids['canadian']:
        ca_entries = c.execute("""
            SELECT id, name, city, moravian_type FROM moravian_hierarchy
            WHERE country = 'CA' AND moravian_type != 'province_hq'
        """).fetchall()
        
        if not dry_run:
            for hid, name, city, mtype in ca_entries:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'administered_by'
                    WHERE id = ?
                """, (hq_ids['canadian'], hid))
        print(f"  Canadian entries linked: {len(ca_entries)}")
    
    # Step 5: Link Jamaican entries to Jamaica Province
    if hq_ids['jamaica']:
        jm_entries = c.execute("""
            SELECT id, name, city, moravian_type FROM moravian_hierarchy
            WHERE country = 'JM' AND moravian_type != 'province_hq'
        """).fetchall()
        
        if not dry_run:
            for hid, name, city, mtype in jm_entries:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'administered_by'
                    WHERE id = ?
                """, (hq_ids['jamaica'], hid))
        print(f"  Jamaican entries linked: {len(jm_entries)}")
    
    # Step 6: Link province board entries under their respective province HQs
    # Board of Elders of the Canadian District → Canadian District (already linked as province_hq)
    # Provincial Women's Board Northern → Northern Province
    board_northern = c.execute("""
        SELECT id FROM moravian_hierarchy
        WHERE church_id IN (3545927, 3545792)  -- Women's Board Northern, Pension Fund
    """).fetchall()
    if hq_ids['northern']:
        for (bid,) in board_northern:
            if not dry_run:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'affiliated_with'
                    WHERE id = ?
                """, (hq_ids['northern'], bid))
        print(f"  Northern boards linked: {len(board_northern)}")
    
    board_southern = c.execute("""
        SELECT id FROM moravian_hierarchy
        WHERE church_id IN (459246)  -- Provincial Women's Board Southern
    """).fetchall()
    if hq_ids['southern']:
        for (bid,) in board_southern:
            if not dry_run:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'affiliated_with'
                    WHERE id = ?
                """, (hq_ids['southern'], bid))
        print(f"  Southern boards linked: {len(board_southern)}")
    
    if not dry_run:
        db.commit()
    
    # North American Boards under Northern Province
    board_na = c.execute("""
        SELECT id FROM moravian_hierarchy
        WHERE church_id IN (45872)  -- Board of World Mission
    """).fetchall()
    if hq_ids['northern']:
        for (bid,) in board_na:
            if not dry_run:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'province_hq', relationship = 'affiliated_with'
                    WHERE id = ?
                """, (hq_ids['northern'], bid))
        print(f"  North American boards linked: {len(board_na)}")


# ========================
# MAIN
# ========================

print("=" * 60)
print("Hierarchy Restructuring")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

hq_ids = {}  # populated by restructure_moravian, used in summary
restructure_chabad()
if not dry_run:
    db.commit()

restructure_moravian()
if not dry_run:
    db.commit()

# Summary
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

# Chabad
chabad_total = c.execute("SELECT COUNT(*) FROM chabad_hierarchy").fetchone()[0]
chabad_linked = c.execute("SELECT COUNT(*) FROM chabad_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
chabad_orphans = c.execute("SELECT COUNT(*) FROM chabad_hierarchy WHERE church_id != 270192 AND parent_id IS NULL").fetchone()[0]
print(f"\nChabad: {chabad_total} rows, {chabad_linked} linked, {chabad_orphans} orphans")

# Chabad top-level children
hq_hid = c.execute("SELECT id FROM chabad_hierarchy WHERE church_id=270192").fetchone()
if hq_hid:
    for r in c.execute("""
        SELECT parent_chabad_type, COUNT(*) FROM chabad_hierarchy
        WHERE parent_id = ? GROUP BY parent_chabad_type
    """, (hq_hid[0],)):
        print(f"  Direct children of HQ (type={r[0]}): {r[1]}")

# Check campus_chabad parent
campus_intl = c.execute("SELECT id FROM chabad_hierarchy WHERE church_id=20513").fetchone()
if campus_intl:
    cc_count = c.execute(
        "SELECT COUNT(*) FROM chabad_hierarchy WHERE parent_id = ?", (campus_intl[0],)
    ).fetchone()[0]
    print(f"  Children of Chabad on Campus International: {cc_count}")

# Moravian
moravian_total = c.execute("SELECT COUNT(*) FROM moravian_hierarchy").fetchone()[0]
moravian_linked = c.execute("SELECT COUNT(*) FROM moravian_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f"\nMoravian: {moravian_total} rows, {moravian_linked} linked, {moravian_total - moravian_linked} unlinked")

# Province-level breakdown
for name, key in [('Northern Province', 'northern'), ('Southern Province', 'southern'),
                   ('Canadian District', 'canadian'), ('Jamaica Province', 'jamaica')]:
    hid = hq_ids.get(key)
    if hid:
        cnt = c.execute(
            "SELECT COUNT(*) FROM moravian_hierarchy WHERE parent_id = ?", (hid,)
        ).fetchone()[0]
        print(f"  Under {name}: {cnt}")

# Check South Africa is no longer linked
za_linked = c.execute("""
    SELECT COUNT(*) FROM moravian_hierarchy h
    WHERE h.country = 'ZA' AND h.parent_id IS NOT NULL
""").fetchone()[0]
print(f"  South Africa entries still incorrectly linked: {za_linked}")

if not dry_run:
    # Log provenance
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at,
                                     churches_updated, records_attempted, status)
        VALUES ('hierarchy_restructure', 'restructure_chabad_moravian_hierarchy.py', ?,
                ?, ?, 'completed')
    """, (now, chabad_linked + moravian_linked, chabad_total + moravian_total))
    db.commit()

db.close()
print("\nDone.")

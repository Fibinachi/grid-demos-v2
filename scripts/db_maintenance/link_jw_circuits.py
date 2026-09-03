"""
Link Kingdom Halls to their regional Assembly Halls by province.
Collapse circuits into ministries JSON on the Assembly Hall.

Physical hierarchy:
  Assembly Hall (regional building)
    ├── ministries: [circuits that hold assemblies here]
    └── Kingdom Hall (served_by → AH)
          └── ministries: [congregations that meet here]

Usage:
    python scripts/db_maintenance/link_jw_circuits.py              # run for real
    python scripts/db_maintenance/link_jw_circuits.py --dry-run     # preview
"""
import sqlite3, json, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=60000")
c = db.cursor()


def normalize(s):
    if s is None:
        return ''
    return s.strip().lower()


print("=" * 60)
print("JW Structural Linking: KH→AH + Circuit→Ministry")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# ── Load data ──
kingdom_halls = c.execute("""
    SELECT id, name, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'kingdom_hall'
    ORDER BY id
""").fetchall()

assembly_halls = c.execute("""
    SELECT id, name, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'assembly_hall'
    ORDER BY id
""").fetchall()

circuits = c.execute("""
    SELECT id, name, jw_detail, circuit_code, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'circuit'
    ORDER BY id
""").fetchall()

print(f"\nLoaded: {len(kingdom_halls):,} KHs, {len(assembly_halls):,} AHs, {len(circuits):,} circuits")

# Build AH lookup by province
ah_lookup = {}
for h in assembly_halls:
    key = (normalize(h[3]), normalize(h[4]))
    ah_lookup.setdefault(key, []).append(h)

print(f"  Assembly halls in {len(ah_lookup)} province+country keys")

# ── Link KHs → AH by province ──
print("\n[1/3] Linking Kingdom Halls to Assembly Halls...")

kh_links = []  # [(kh_id, ah_id, ah_name), ...]
kh_unlinked = 0

for kh in kingdom_halls:
    khid, khname, khcity, khstate, khcountry = kh
    key = (normalize(khstate), normalize(khcountry))
    candidates = ah_lookup.get(key, [])
    
    if len(candidates) == 1:
        kh_links.append((khid, candidates[0][0], candidates[0][1]))
    elif len(candidates) > 1:
        # Multiple AHs in same province — link to first (city-match preferred)
        best = None
        for h in candidates:
            if khcity and normalize(h[2]) == normalize(khcity):
                best = h
                break
        if not best:
            best = candidates[0]
        kh_links.append((khid, best[0], best[1]))
    else:
        kh_unlinked += 1

print(f"  Linked: {len(kh_links):,} KHs | Unlinked: {kh_unlinked:,}")

# ── Collapse circuits → ministries on AH ──
print("\n[2/3] Collapsing circuits into ministries on Assembly Halls...")

circuit_moves = []  # [(ah_id, [ministry_dicts]), ...]
circuit_unlinked = []

for circ in circuits:
    cid, cname, cdetail, ccode, ccity, cstate, ccountry = circ
    key = (normalize(cstate), normalize(ccountry))
    candidates = ah_lookup.get(key, [])
    
    ministry = {'type': 'circuit', 'name': cname}
    if cdetail:
        ministry['detail'] = cdetail
    if ccode:
        ministry['circuit_code'] = ccode
    if ccity:
        ministry['city'] = ccity
    
    if len(candidates) >= 1:
        # Attach to first AH in province (or city-match if possible)
        best = None
        for h in candidates:
            if ccity and normalize(h[2]) == normalize(ccity):
                best = h
                break
        if not best:
            best = candidates[0]
        circuit_moves.append((best[0], ministry))
    else:
        circuit_unlinked.append(circ)

print(f"  Collapsed: {len(circuit_moves)} circuits onto AHs")
if circuit_unlinked:
    print(f"  Unlinked: {len(circuit_unlinked)} circuits (no AH in province)")

# ── Apply ──
print("\n[3/3] Applying changes...")

if dry_run:
    print(f"  Would update {len(kh_links):,} KHs (parent_id → AH, relationship='served_by')")
    print(f"  Would collapse {len(circuit_moves)} circuits into AH ministries JSON")
    print(f"  Would delete {len(circuits)} circuit rows")
else:
    # Update KHs: parent_id + relationship
    kh_batch = []
    for khid, ahid, ahname in kh_links:
        kh_batch.append((ahid, khid))
        if len(kh_batch) >= CHUNK:
            c.executemany(
                "UPDATE jw_hierarchy SET parent_id = ?, relationship = 'served_by' WHERE id = ?",
                kh_batch
            )
            db.commit()
            kh_batch = []
    if kh_batch:
        c.executemany(
            "UPDATE jw_hierarchy SET parent_id = ?, relationship = 'served_by' WHERE id = ?",
            kh_batch
        )
        db.commit()
    print(f"  ✓ Updated {len(kh_links):,} KHs with parent_id → AH")
    
    # Collapse circuits: append to AH ministries JSON
    ah_updates = {}  # {ah_id: [ministry_dicts]}
    for ahid, ministry in circuit_moves:
        ah_updates.setdefault(ahid, []).append(ministry)
    
    updated_ahs = 0
    for ahid, ministries in ah_updates.items():
        existing = c.execute(
            "SELECT ministries FROM jw_hierarchy WHERE id = ?", (ahid,)
        ).fetchone()[0]
        
        if existing:
            existing_list = json.loads(existing)
            existing_list.extend(ministries)
            combined = json.dumps(existing_list, ensure_ascii=False)
        else:
            combined = json.dumps(ministries, ensure_ascii=False)
        
        c.execute("UPDATE jw_hierarchy SET ministries = ? WHERE id = ?", (combined, ahid))
        updated_ahs += 1
    db.commit()
    print(f"  ✓ Updated {updated_ahs} AHs with circuit ministries")
    
    # Delete circuit rows
    c.execute("DELETE FROM jw_hierarchy WHERE jw_type = 'circuit'")
    db.commit()
    print(f"  ✓ Deleted {c.rowcount} circuit rows")
    
    # Verify
    cnt = c.execute("SELECT COUNT(*) FROM jw_hierarchy").fetchone()[0]
    print(f"\n  Final rows: {cnt:,}")
    
    linked = c.execute("SELECT COUNT(*) FROM jw_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
    print(f"  With parent_id: {linked:,}")
    
    mins_count = c.execute("SELECT COUNT(*) FROM jw_hierarchy WHERE ministries IS NOT NULL").fetchone()[0]
    print(f"  With ministries: {mins_count}")
    
    rels = c.execute(
        "SELECT relationship, COUNT(*) FROM jw_hierarchy WHERE relationship IS NOT NULL GROUP BY relationship"
    ).fetchall()
    for r, cnt in rels:
        print(f"    {r}: {cnt}")

db.close()
print("\nDone.")

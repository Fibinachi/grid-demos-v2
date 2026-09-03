"""
Collapse JW congregations into a JSON 'ministries' column on their parent KH.

Congregations are ministries that meet in a Kingdom Hall building — they don't
have independent physical existence. Instead of modeling them as separate rows
in jw_hierarchy, store them as a JSON array on the KH row.

Strategy:
1. Add `ministries` TEXT column (JSON array) to jw_hierarchy
2. Match congregations to KHs by city+state+country
3. For multi-match cities, try detail-based disambiguation
4. Serialize matched congregations into JSON on the KH row
5. Delete all congregation rows from jw_hierarchy

Usage:
    python scripts/db_maintenance/collapse_jw_congregations.py     # run for real
    python scripts/db_maintenance/collapse_jw_congregations.py --dry-run   # preview
"""
import sqlite3, json, re, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

def normalize(s):
    """Normalize a string for comparison."""
    if s is None:
        return ''
    return s.strip().lower()

def make_ministry_json(cong):
    """Serialize a congregation row into a ministry dict."""
    ministry = {}
    if cong[1]:  # name
        ministry['name'] = cong[1]
    if cong[2]:  # jw_detail (congregation name like "ACACIA")
        ministry['detail'] = cong[2]
    if cong[3]:  # circuit_code
        ministry['circuit'] = cong[3]
    if cong[4]:  # church_id (for back-linking)
        ministry['church_id'] = cong[4]
    return ministry

def try_detail_match(cong_detail, khs):
    """Try to match a congregation to a specific KH by detail keyword."""
    if not cong_detail:
        return None
    cd = normalize(cong_detail)
    for kh in khs:
        # Check if detail appears in KH name or jw_detail
        kh_name = normalize(kh[1])
        kh_detail = normalize(kh[2])
        if cd in kh_name or (kh_detail and cd in kh_detail):
            return kh
    return None

print("=" * 60)
print("JW Congregation Collapse — Ministries JSON")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# ── Step 1: Add ministries column ──
print("\n[1/4] Adding ministries column...")
try:
    c.execute("ALTER TABLE jw_hierarchy ADD COLUMN ministries TEXT")
    print("  Column 'ministries' added.")
    if not dry_run:
        db.commit()
except sqlite3.OperationalError as e:
    if 'duplicate column' in str(e).lower():
        print("  Column 'ministries' already exists.")
    else:
        raise

# ── Step 2: Load all congregations and KHs ──
print("\n[2/4] Loading data...")

congregations = c.execute("""
    SELECT id, name, jw_detail, circuit_code, church_id,
           city, state, country, lat, lon
    FROM jw_hierarchy
    WHERE jw_type = 'congregation'
    ORDER BY id
""").fetchall()
print(f"  Loaded {len(congregations):,} congregations")

kingdom_halls = c.execute("""
    SELECT id, name, jw_detail, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'kingdom_hall'
    ORDER BY id
""").fetchall()
print(f"  Loaded {len(kingdom_halls):,} Kingdom Halls")

# Build KH lookup: {(city_norm, state_norm, country_norm): [(id, name, detail), ...]}
kh_lookup = {}
for kh in kingdom_halls:
    key = (normalize(kh[3]), normalize(kh[4]), normalize(kh[5]))
    kh_lookup.setdefault(key, []).append(kh)

print(f"  Built lookup for {len(kh_lookup):,} unique city+state+country keys")

# ── Step 3: Match congregations to KHs ──
print("\n[3/4] Matching congregations to Kingdom Halls...")

matched = 0      # matched to exactly 1 KH
multi = 0        # matched to multiple KHs
detail_resolved = 0  # resolved multi-match via detail
no_match = 0     # no KH found in same city
updates = {}     # {kh_id: [ministry_dict, ...]}

for cong in congregations:
    cong_id, name, detail, circ_code, ch_id, city, state, country = cong[:8]
    key = (normalize(city), normalize(state), normalize(country))
    candidates = kh_lookup.get(key, [])
    
    if len(candidates) == 1:
        # Exact match — attach to this KH
        kh = candidates[0]
        updates.setdefault(kh[0], []).append(make_ministry_json(cong))
        matched += 1
    elif len(candidates) > 1:
        # Try detail-based disambiguation
        kh = try_detail_match(detail, candidates)
        if kh:
            updates.setdefault(kh[0], []).append(make_ministry_json(cong))
            detail_resolved += 1
        else:
            # No clear match — attach to first KH with a note
            ministry = make_ministry_json(cong)
            ministry['_ambiguous'] = True
            updates.setdefault(candidates[0][0], []).append(ministry)
            multi += 1
    else:
        no_match += 1

print(f"  Exactly matched:  {matched:>5}")
print(f"  Detail-resolved:  {detail_resolved:>5}")
print(f"  Multi (ambiguous): {multi:>5}")
print(f"  No match:         {no_match:>5}")
print(f"  KHs receiving ministries: {len(updates):,}")

# ── Step 4: Apply updates and delete congregation rows ──
print("\n[4/4] Applying changes...")

if dry_run:
    print("  (skipped — dry run)")
    print(f"  Would update {len(updates)} KHs with ministries JSON")
    print(f"  Would delete {len(congregations)} congregation rows")
    
    # Show sample
    print("\n  Sample update (first 5 KHs):")
    for i, (kh_id, ministries) in enumerate(updates.items()):
        if i >= 5:
            break
        kh_name = c.execute("SELECT name FROM jw_hierarchy WHERE id=?", (kh_id,)).fetchone()[0]
        print(f"    KH #{kh_id}: {kh_name[:50]}")
        for m in ministries[:3]:
            print(f"      → {m.get('name', '?')[:50]}")
        if len(ministries) > 3:
            print(f"      ... and {len(ministries)-3} more")
else:
    # Batch update KHs
    print(f"  Updating {len(updates)} KHs with ministries JSON...")
    
    batch = []
    for kh_id, ministries in updates.items():
        batch.append((json.dumps(ministries, ensure_ascii=False), kh_id))
        if len(batch) >= CHUNK:
            c.executemany(
                "UPDATE jw_hierarchy SET ministries = ? WHERE id = ?",
                batch
            )
            db.commit()
            batch = []
            print(f"    Updated {len(updates)}/{len(updates)}...", end='\r', flush=True)
    
    if batch:
        c.executemany(
            "UPDATE jw_hierarchy SET ministries = ? WHERE id = ?",
            batch
        )
        db.commit()
    print(f"    Updated {len(updates)} KHs.             ")
    
    # Delete congregation rows
    print(f"  Deleting {len(congregations)} congregation rows...")
    c.execute("DELETE FROM jw_hierarchy WHERE jw_type = 'congregation'")
    db.commit()
    print(f"    Deleted {c.rowcount:,} rows.")
    
    # Verify
    remaining = c.execute("SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type = 'congregation'").fetchone()[0]
    print(f"  Remaining congregation rows: {remaining}")
    
    # Summary
    kh_with_ministries = c.execute("SELECT COUNT(*) FROM jw_hierarchy WHERE ministries IS NOT NULL").fetchone()[0]
    total_ministries = c.execute("""
        SELECT SUM(json_array_length(ministries)) FROM jw_hierarchy WHERE ministries IS NOT NULL
    """).fetchone()[0]
    print(f"\n  KHs with ministries: {kh_with_ministries}")
    print(f"  Total ministries stored: {total_ministries:,}")

db.close()
print("\nDone.")

"""
Remove misclassified non-JW entries from jw_hierarchy.

Spanish/Portuguese evangelical churches with "Jehovah" in their name
(e.g., "IGLESIA CRISTIANA Jehovah's ES MI PASTOR") are NOT Kingdom Halls.
These need to be removed from the hierarchy.

Strategy:
1. Identify all non-JW patterns using a comprehensive exclusion list
2. For any with ministries attached, try to re-home them to a real KH in the same city
3. Delete all fake entries

Usage:
    python scripts/db_maintenance/cleanup_fake_jw.py              # run for real
    python scripts/db_maintenance/cleanup_fake_jw.py --dry-run     # preview
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
    if s is None:
        return ''
    return s.strip().lower()

# Non-JW patterns that should NOT be in jw_hierarchy
# These are evangelical/Pentecostal churches that use "Jehovah" biblically
NON_JW_PATTERNS = [
    # Spanish evangelical churches
    'iglesia', 'iglesia cristiana', 'iglesia evangelica', 'iglesia de dios',
    'iglesia de cristo', 'iglesia apostoles', 'iglesia profetica',
    'centro cristiano', 'centro evangelistico',
    'ministerio de dios', 'ministerio cristiano',
    'mision profetica', 'mision cristiana',
    'puerta de', 'rocas de', 'roca de',
    'el buen pastor', 'el gran yo soy',
    'fuente de', 'predicando', 'tsidekenu',
    'mi roca', 'mi salvacion', 'es mi guerrero', 'es mi pastor',
    'jesucristo', 'cristo',
    'santidad a jehova', 'santidad a jehovah',
    'avivamiento', 'campamento de jehovah',
    'en el monte sinai',
    'alianza', 'guerreros de',
    # Portuguese
    'igreja',
    # English non-JW
    'rock of ages', 'rock of ages',
    'bear witness church',
    # Hebrew names used by non-JW churches
    'shalom', 'shammah', 'rapha', 'jireh', 'nissi',
    'roi', 'roh', 'sama',
    # Other clearly non-JW
    'jehovah rophe', 'jehovah jireh', 'jehovah nissi', 'jehovah shalom',
    'jehovah shammah', 'jehovah rapha', 'jehovah tsidkenu',
    'jehovah rohi', 'jehovah raah', 'jehovah shama',
    'jehovah m\'kaddesh', 'jehovah mekaddesh',
    'jehovah proveera',
    'jehovah es mi', 'jehovah es mi',
    'la gloria de jehovah',
    'ciudad deceada',
]

# Build a combined regex for SQL exclusion
# We'll use a Python-side filter for the WHERE clause
# But SQL doesn't easily do case-insensitive pattern matching for many patterns
# So we'll filter in Python

def is_fake_jw(name):
    """Check if a name matches a non-JW pattern."""
    if not name:
        return False
    low = name.lower()
    for pat in NON_JW_PATTERNS:
        if pat in low:
            return True
    return False

print("=" * 60)
print("JW Fake Entry Cleanup")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# ── Step 1: Find all fake entries ──
print("\n[1/4] Finding misclassified entries...")

# Get all non-KH entries too (circuit, bethel, etc.) that might be fake
rows = c.execute("""
    SELECT id, name, jw_type, city, state, country, church_id, ministries
    FROM jw_hierarchy
    ORDER BY name
""").fetchall()

fake_entries = []
for r in rows:
    if is_fake_jw(r[1]):
        fake_entries.append(r)

print(f"  Found {len(fake_entries):,} potentially misclassified entries")

# Group by type
type_counts = {}
for r in fake_entries:
    type_counts[r[2]] = type_counts.get(r[2], 0) + 1
for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"    {t:20s}: {cnt:>4}")

# ── Step 2: Check for fake KHs with ministries ──
print("\n[2/4] Checking for orphaned ministries...")

fake_with_ministries = [r for r in fake_entries if r[2] == 'kingdom_hall' and r[7] is not None]
print(f"  Fake KHs with ministries: {len(fake_with_ministries)}")

# For each, try to find a real KH in the same city
# Note: state matching is unreliable (many KHs have NULL state), so match on city+country only
rehomed = 0
orphaned = 0
ministry_moves = []  # [(source_id, target_id, ministries_json), ...]

for r in fake_with_ministries:
    fid, fname, ftype, fcity, fstate, fcountry, fch_id, fmins = r
    mins_data = json.loads(fmins)
    
    if not fcity:
        # No city — can't rehome
        orphaned += len(mins_data)
        continue
    
    # Find a real KH in the same city+country (state is unreliable)
    real_kh = c.execute("""
        SELECT id, name FROM jw_hierarchy
        WHERE jw_type = 'kingdom_hall'
          AND id != ?
          AND LOWER(TRIM(city)) = ?
          AND LOWER(TRIM(COALESCE(country, ''))) = ?
          AND name NOT LIKE '%IGLESIA%' AND name NOT LIKE '%IGREJA%'
          AND name LIKE '%Kingdom%Hall%'
        LIMIT 1
    """, (fid, normalize(fcity), normalize(fcountry))).fetchone()
    if real_kh:
        ministry_moves.append((fid, real_kh[0], fmins))
        rehomed += len(mins_data)
    else:
        orphaned += len(mins_data)

print(f"  Ministries to rehome: {rehomed}")
print(f"  Ministries orphaned (no real KH nearby): {orphaned}")

# ── Step 3: Apply changes ──
print("\n[3/4] Applying changes...")

if dry_run:
    print("  (skipped — dry run)")
    print(f"  Would rehome {rehomed} ministries to real KHs")
    print(f"  Would delete {len(fake_entries)} fake entries")
    print(f"    (including {len(fake_with_ministries)} KHs with ministries)")
else:
    # Rehome ministries
    if ministry_moves:
        print(f"  Rehoming {rehomed} ministries...")
        for source_id, target_id, mins_json in ministry_moves:
            # Append to target's existing ministries
            existing = c.execute(
                "SELECT ministries FROM jw_hierarchy WHERE id = ?", (target_id,)
            ).fetchone()[0]
            
            new_mins = json.loads(mins_json)
            if existing:
                existing_mins = json.loads(existing)
                existing_mins.extend(new_mins)
                combined = json.dumps(existing_mins, ensure_ascii=False)
            else:
                combined = mins_json
            
            c.execute(
                "UPDATE jw_hierarchy SET ministries = ? WHERE id = ?",
                (combined, target_id)
            )
        db.commit()
        print(f"    Rehomed to {len(set(m[1] for m in ministry_moves)):,} KHs")
    
    # Clear ministries from fake KHs before deleting
    fake_ids = [r[0] for r in fake_entries]
    batch = []
    for fid in fake_ids:
        batch.append((fid,))
        if len(batch) >= CHUNK:
            c.executemany(
                "UPDATE jw_hierarchy SET ministries = NULL WHERE id = ?", batch
            )
            batch = []
    if batch:
        c.executemany(
            "UPDATE jw_hierarchy SET ministries = NULL WHERE id = ?", batch
        )
    db.commit()
    
    # Delete fake entries
    print(f"  Deleting {len(fake_entries)} fake entries...")
    batch = []
    for fid in fake_ids:
        batch.append((fid,))
        if len(batch) >= CHUNK:
            c.executemany("DELETE FROM jw_hierarchy WHERE id = ?", batch)
            batch = []
    if batch:
        c.executemany("DELETE FROM jw_hierarchy WHERE id = ?", batch)
    db.commit()
    print(f"    Deleted.")

# ── Step 4: Verify ──
print("\n[4/4] Verification...")
remaining = c.execute("SELECT COUNT(*) FROM jw_hierarchy").fetchone()[0]
print(f"  Remaining rows: {remaining:,}")

# Check no fake patterns remain
still_fake = 0
for r in c.execute("SELECT id, name FROM jw_hierarchy").fetchall():
    if is_fake_jw(r[1]):
        still_fake += 1
print(f"  Remaining fake entries: {still_fake}")

db.close()
print("\nDone.")

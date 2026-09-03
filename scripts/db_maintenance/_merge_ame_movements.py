"""
Merge duplicate movements and backfill churches.
1. Add missing movements (Church of the Living God)
2. Merge AME duplicates
3. Backfill churches
"""
import sqlite3, time

DB_PATH = r'E:\grid\churches.db'
db = sqlite3.connect(DB_PATH)
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')
c = db.cursor()

def log(msg):
    print(f'  {msg}')

# ========================
# STEP 1: Add Church of the Living God movement
# ========================
print('=== STEP 1: Church of the Living God ===')

# Get tradition ID for Pentecostal
pent = c.execute("SELECT id FROM tradition WHERE name='Pentecostal'").fetchone()
if not pent:
    # Try Holiness
    pent = c.execute("SELECT id FROM tradition WHERE name='Holiness'").fetchone()
tradition_id = pent[0] if pent else None
print(f'  Parent tradition: {tradition_id} (Pentecostal)')

# Check if already exists
existing = c.execute("SELECT id FROM movement WHERE name='Church of the Living God'").fetchone()
if existing:
    print(f'  Already exists: id={existing[0]}')
    clg_id = existing[0]
else:
    max_id = c.execute("SELECT MAX(id) FROM movement").fetchone()[0]
    clg_id = max_id + 1
    c.execute("""
        INSERT INTO movement (id, name, tradition_id, description)
        VALUES (?, 'Church of the Living God', ?, 
        'Holiness/Pentecostal denomination founded by Mother Mary Magdalena Lewis Tate in 1903. Includes branches: Pillar and Ground of the Truth, Christian Workers for Fellowship, International.')
    """, (clg_id, tradition_id))
    db.commit()
    print(f'  Created movement id={clg_id}: Church of the Living God')

# ========================
# STEP 2: Merge AME duplicate movements
# ========================
print()
print('=== STEP 2: Merge AME movements ===')

# Map: duplicate_id -> canonical_id
ame_merges = {}

# AME (367) is canonical for "African Methodist Episcopal"
canon_ame = c.execute("SELECT id FROM movement WHERE name='AME'").fetchone()
if canon_ame:
    canon_ame = canon_ame[0]
    for dup_name in ['African Methodist Episcopal', 'African Methodist Episcopal Church']:
        dup = c.execute("SELECT id FROM movement WHERE name=?", (dup_name,)).fetchone()
        if dup and dup[0] != canon_ame:
            ame_merges[dup[0]] = canon_ame
            n = c.execute("SELECT COUNT(*) FROM churches WHERE movement_id=?", (dup[0],)).fetchone()[0]
            print(f'  Merge {dup_name} (id={dup[0]}, {n} churches) → AME (id={canon_ame})')

# AME Zion (368) is canonical for "AME Zion"
canon_amez = c.execute("SELECT id FROM movement WHERE name='AME Zion'").fetchone()
if canon_amez:
    canon_amez = canon_amez[0]
    dup = c.execute("SELECT id FROM movement WHERE name='African Methodist Episcopal Zion Church'").fetchone()
    if dup and dup[0] != canon_amez:
        ame_merges[dup[0]] = canon_amez
        n = c.execute("SELECT COUNT(*) FROM churches WHERE movement_id=?", (dup[0],)).fetchone()[0]
        print(f'  Merge African Methodist Episcopal Zion Church (id={dup[0]}, {n} churches) → AME Zion (id={canon_amez})')

# Execute merges
for dup_id, canon_id in ame_merges.items():
    n = c.execute("UPDATE churches SET movement_id=? WHERE movement_id=?", (canon_id, dup_id)).rowcount
    c.execute("DELETE FROM movement WHERE id=?", (dup_id,))
    print(f'  Updated {n} churches, deleted movement {dup_id}')
db.commit()

# ========================
# STEP 3: Backfill AME churches
# ========================
print()
print('=== STEP 3: Backfill AME churches ===')

# Get canonical IDs
ame_id = c.execute("SELECT id FROM movement WHERE name='AME'").fetchone()[0]
amez_id = c.execute("SELECT id FROM movement WHERE name='AME Zion'").fetchone()[0]
methodist_id = c.execute("SELECT id FROM tradition WHERE name='Methodist'").fetchone()[0]
print(f'  AME movement id={ame_id}, AME Zion id={amez_id}')

# Backfill AME (not Zion)
ame_patterns = [
    "% A.M.E. Church%", "% A.M.E. CHURCH%",
    "%African Methodist Episcopal Church%", "%AFRICAN METHODIST EPISCOPAL CHURCH%",
    "%African Methodist Episcopal%",
]
for pat in ame_patterns:
    # Only update where NOT already AME or AME Zion
    n = c.execute("""
        UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
        landmark_type=COALESCE(landmark_type, 'church')
        WHERE faith='Christian' AND country='US'
        AND movement_id IS NULL
        AND name LIKE ?
        AND name NOT LIKE '%Zion%'
    """, (ame_id, methodist_id, c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0], pat)).rowcount
    if n:
        print(f'  {pat}: {n} churches backfilled')

# Backfill AME Zion
amez_patterns = [
    "% A.M.E. Zion%", "% AME Zion%", "% A.M.E. ZION%",
    "%African Methodist Episcopal Zion%",
]
for pat in amez_patterns:
    n = c.execute("""
        UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
        landmark_type=COALESCE(landmark_type, 'church')
        WHERE faith='Christian' AND country='US'
        AND movement_id IS NULL
        AND name LIKE ?
    """, (amez_id, methodist_id, c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0], pat)).rowcount
    if n:
        print(f'  {pat}: {n} churches backfilled')

db.commit()

# ========================
# STEP 4: Backfill Church of the Living God
# ========================
print()
print('=== STEP 4: Backfill Church of the Living God ===')
n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian'
    AND movement_id IS NULL
    AND name LIKE '%Church of the Living God%'
""", (clg_id, tradition_id, c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0])).rowcount
print(f'  {n} churches backfilled')
db.commit()

# ========================
# STEP 5: Also backfill "AME Church" simple pattern
# ========================
print()
print('=== STEP 5: Remaining AME catch-all ===')
n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND country='US'
    AND movement_id IS NULL
    AND (name LIKE '% AME %' OR name LIKE '% A.M.E. %')
    AND name NOT LIKE '%Zion%'
""", (ame_id, methodist_id, c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0])).rowcount
print(f'  {n} more AME churches backfilled')

n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND country='US'
    AND movement_id IS NULL
    AND (name LIKE '% AME Zion%' OR name LIKE '% A.M.E. Zion%' OR name LIKE '% A.M.E. ZION%')
""", (amez_id, methodist_id, c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0])).rowcount
print(f'  {n} more AME Zion churches backfilled')
db.commit()

# ========================
# STEP 6: Verify
# ========================
print()
print('=== Verification ===')

# Count remaining unclassified AME churches
remaining = c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Christian' AND country='US'
    AND movement_id IS NULL
    AND (name LIKE '% A.M.E.%' OR name LIKE '%African Methodist Episcopal%')
""").fetchone()[0]
print(f'  Remaining unclassified AME (US): {remaining}')

# Final AME totals
for name in ['AME', 'AME Zion', 'Church of the Living God']:
    mv = c.execute("SELECT id FROM movement WHERE name=?", (name,)).fetchone()
    if mv:
        n = c.execute("SELECT COUNT(*) FROM churches WHERE movement_id=?", (mv[0],)).fetchone()[0]
        print(f'  {name}: {n:,} churches')

db.close()
print()
print('DONE')

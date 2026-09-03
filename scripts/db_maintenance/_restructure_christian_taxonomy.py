"""
Restructure Christian taxonomy to 4-level model:

  Christian
    ├── Catholic
    ├── Orthodox
    ├── Protestant (Baptist/Methodist/Pentecostal/etc.)
    ├── Anglican
    ├── Restorationist (NEW)
    │   ├── Churches of Christ
    │   │   ├── Church of Christ
    │   │   ├── Christian Church
    │   │   ├── Christian Church (Disciples of Christ)
    │   │   └── ...
    │   └── (future: other restoration bodies)
    └── Other (NEW)
        ├── Latter-day Saints
        │   ├── LDS
        │   ├── Community of Christ
        │   └── FLDS
        └── Jehovah's Witnesses

Columns: faith(L1) → legacy(L2=historic schism) → tradition(L3=movement) → denomination(L4)
"""
import sqlite3, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
try:
    from gw_db import get_db
    db = get_db()
except ImportError:
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), "churches.db"))
c = db.cursor()
start = time.time()

def update_paths(c, parent_id, new_base):
    """Recursively update full_path for all children of parent_id"""
    c.execute("SELECT id, name FROM taxonomy WHERE parent_id = ?", (parent_id,))
    children = c.fetchall()
    for child_id, name in children:
        new_path = f"{new_base}/{name}"
        c.execute("UPDATE taxonomy SET full_path = ? WHERE id = ?", (new_path, child_id))
        update_paths(c, child_id, new_path)

def get_next_id(c):
    c.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM taxonomy")
    return c.fetchone()[0]

# === STEP 1: Create new L2 nodes ===
print("=== Step 1: Creating Restorationist + Other ===")

rest_id = get_next_id(c)
c.execute("INSERT INTO taxonomy (id, parent_id, name, full_path) VALUES (?, 2, 'Restorationist', 'Christian/Restorationist')", (rest_id,))
print(f"  Created ID {rest_id}: Christian/Restorationist")

other_id = get_next_id(c)
c.execute("INSERT INTO taxonomy (id, parent_id, name, full_path) VALUES (?, 2, 'Other', 'Christian/Other')", (other_id,))
print(f"  Created ID {other_id}: Christian/Other")

# === STEP 2: Move Churches of Christ under Restorationist ===
print("\n=== Step 2: Moving Churches of Christ → Restorationist ===")

# ID 210 = Christian/Protestant/Churches of Christ (currently parent=19)
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = 210")
on_210 = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path LIKE 'Christian/Protestant/Churches of Christ/%')")
under_210 = c.fetchone()[0]
print(f"  Churches directly at ID 210: {on_210}")
print(f"  Churches under ID 210 children: {under_210}")

c.execute("UPDATE taxonomy SET parent_id = ?, full_path = 'Christian/Restorationist/Churches of Christ' WHERE id = 210", (rest_id,))
update_paths(c, 210, "Christian/Restorationist/Churches of Christ")
print(f"  Moved Churches of Christ (ID 210) → Restorationist")

# Also update church records - these now have legacy='Restorationist' 
# but what about tradition? ID 210 is L3, children like 317 are L4
# Let me update legacy for all churches under this branch
c.execute("""
    UPDATE churches SET legacy = 'Restorationist'
    WHERE taxonomy_id IN (
        SELECT id FROM taxonomy 
        WHERE full_path LIKE 'Christian/Restorationist/%'
    )
""")
print(f"  Updated {c.rowcount} churches → legacy=Restorationist")

# === STEP 3: Move Latter-day Saints under Other ===
print("\n=== Step 3: Moving Latter-day Saints → Other ===")

c.execute("UPDATE taxonomy SET parent_id = ?, full_path = 'Christian/Other/Latter-day Saints' WHERE id = 17", (other_id,))
# Update all descendants
update_paths(c, 17, "Christian/Other/Latter-day Saints")
print(f"  Moved Latter-day Saints (ID 17) → Other")

# Fix the redundant LDS/LDS path (ID 456 = LDS/LDS, should merge into ID 168)
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = 456")
on_456 = c.fetchone()[0]
if on_456 > 0:
    c.execute("UPDATE churches SET taxonomy_id = 168 WHERE taxonomy_id = 456")
    print(f"  Merged {c.rowcount} churches from ID 456 → 168 (LDS)")

# Fix Community of Christ and FLSD to be directly under Latter-day Saints
c.execute("UPDATE taxonomy SET parent_id = 17, full_path = 'Christian/Other/Latter-day Saints/Community of Christ' WHERE id = 167")
c.execute("UPDATE taxonomy SET parent_id = 17, full_path = 'Christian/Other/Latter-day Saints/FLDS' WHERE id = 458")
# Fix Other LDS (ID 457) - move orphans to LDS default
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = 457")
on_457 = c.fetchone()[0]
if on_457 > 0:
    c.execute("UPDATE churches SET taxonomy_id = 17 WHERE taxonomy_id = 457")
    print(f"  Merged {c.rowcount} churches from ID 457 → 17 (Latter-day Saints)")
print("  Fixed Community of Christ + FLDS under Latter-day Saints")

# Update church legacy
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Latter-day Saints'
    WHERE taxonomy_id IN (168, 167, 458) 
""")
print(f"  Updated {c.rowcount} LDS churches → legacy=Other, tradition=Latter-day Saints")

# === STEP 4: Move Jehovah's Witnesses under Other ===
print("\n=== Step 4: Moving Jehovah's Witnesses → Other ===")

c.execute("UPDATE taxonomy SET parent_id = ?, full_path = 'Christian/Other/Jehovah''s Witnesses' WHERE id = 16", (other_id,))
update_paths(c, 16, "Christian/Other/Jehovah's Witnesses")
print(f"  Moved JW (ID 16) → Other")

# Update JW church records
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Jehovah''s Witnesses'
    WHERE taxonomy_id IN (16, 165)
""")
print(f"  Updated {c.rowcount} JW churches → legacy=Other, tradition=Jehovah's Witnesses")

# Fix misclassified JW records (name says JW but wrong taxonomy)
c.execute("""
    UPDATE churches SET taxonomy_id = 165, legacy = 'Other', tradition = 'Jehovah''s Witnesses'
    WHERE (name LIKE '%Jehovah%Witness%' OR name LIKE '%Kingdom Hall%' OR tradition = 'jehovahs_witness')
      AND taxonomy_id NOT IN (16, 165)
""")
print(f"  Fixed {c.rowcount} misclassified JW records")

db.commit()

# === Cleanup: remove orphaned taxonomy entries ===
print("\n=== Step 5: Cleanup ===")
# Delete ID 456 if no churches use it
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = 456")
if c.fetchone()[0] == 0:
    c.execute("DELETE FROM taxonomy WHERE id = 456")
    print("  Deleted orphaned taxonomy ID 456 (LDS/LDS)")

c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = 457")
if c.fetchone()[0] == 0:
    c.execute("DELETE FROM taxonomy WHERE id = 457")
    print("  Deleted orphaned taxonomy ID 457 (Other LDS)")

db.commit()

# === VERIFICATION ===
print("\n=== FINAL VERIFICATION ===")
print("\nChristian children (L2):")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE parent_id = 2 ORDER BY id")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path LIKE ? || '%')", (r[2],))
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    direct = c.fetchone()[0]
    print(f"  ID {r[0]:>3}: {r[1]:20s} direct={direct:>6,} total_incl_children={total:>7,}  ({r[2]})")

print("\nRestorationist branch:")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE full_path LIKE 'Christian/Restorationist%' ORDER BY full_path")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]:>3}: {r[2]:70s} — {c.fetchone()[0]:>7,} churches")

print("\nOther branch:")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE full_path LIKE 'Christian/Other%' ORDER BY full_path")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]:>3}: {r[2]:70s} — {c.fetchone()[0]:>7,} churches")

print(f"\nTotal time: {time.time()-start:.1f}s")
db.close()
print("Done!")

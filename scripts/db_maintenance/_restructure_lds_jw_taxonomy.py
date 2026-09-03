"""
Restructure LDS + JW under Christian/Other with proper 4-level columns.

The 4-level model:
  faith (L1) → legacy (L2=historic schism) → tradition (L3=movement) → denomination (L4)

For LDS/JW:
  faith=Christian, legacy=Other, tradition=Latter-day Saints/Jehovah's Witnesses, denomination=specific
"""
import sqlite3, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
try:
    from gw_db import get_db
    db = get_db()
    provenance = True
except ImportError:
    db = sqlite3.connect(os.path.join(os.path.dirname(__file__), "churches.db"))
    provenance = False
c = db.cursor()
start = time.time()

# Check current JW state
print("=== Current JW taxonomy ===")
c.execute("""
    SELECT id, parent_id, name, full_path
    FROM taxonomy
    WHERE full_path LIKE '%Jehovah%'
    ORDER BY id
""")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]}: {r[3]} — {c.fetchone()[0]} churches")

print("\n=== Current LDS taxonomy ===")
c.execute("""
    SELECT id, parent_id, name, full_path
    FROM taxonomy
    WHERE full_path LIKE '%Latter-day Saints%'
    ORDER BY id
""")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]}: {r[3]} — {c.fetchone()[0]} churches")

# Step 1: Create Christian/Other node
print("\n=== Step 1: Creating Christian/Other ===")
c.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM taxonomy")
other_id = c.fetchone()[0]

c.execute("""
    INSERT INTO taxonomy (id, parent_id, name, full_path)
    VALUES (?, 2, 'Other', 'Christian/Other')
""", (other_id,))
print(f"  Created taxonomy ID {other_id}: Christian/Other")

# Step 2: Move Latter-day Saints under Other
print("\n=== Step 2: Moving Latter-day Saints under Other ===")
# Update parent_id for Latter-day Saints (ID 17)
c.execute("UPDATE taxonomy SET parent_id = ?, full_path = 'Christian/Other/Latter-day Saints' WHERE id = 17", (other_id,))
print(f"  Moved ID 17 → Christian/Other/Latter-day Saints")

# Update LDS children paths
# ID 456: Christian/Other/Latter-day Saints/LDS/LDS → Christian/Other/Latter-day Saints/LDS
# But wait - we have 4 levels now so LDS/LDS should become just LDS at L4
# Actually the current path is Christian/Latter-day Saints/LDS/LDS
# With parent change to Other, it becomes Christian/Other/Latter-day Saints/LDS/LDS (5 levels!)
# That's too deep. Let me fix this.

# Currently:
# ID 17: Christian/Latter-day Saints → Christian/Other/Latter-day Saints (L3)
# ID 168: Christian/Latter-day Saints/LDS → Christian/Other/Latter-day Saints/LDS (L4 - denomination level!)
# ID 456: Christian/Latter-day Saints/LDS/LDS → Christian/Other/Latter-day Saints/LDS/LDS (5 levels - too deep)

# The 4-level model says: faith/legacy/tradition/denom
# So: Christian/Other/Latter-day Saints/LDS → L4 denomination="LDS"
# And: Christian/Other/Latter-day Saints/Community of Christ → L4 denomination="Community of Christ"
# The extra level "LDS/LDS" needs to collapse.

# ID 456 (Christian/Latter-day Saints/LDS/LDS) should become just Christian/Other/Latter-day Saints/LDS
# But its parent is 168 (Christian/Latter-day Saints/LDS), which is now Christian/Other/Latter-day Saints/LDS
# Wait, ID 168 IS the LDS level. And ID 456 is a duplicate LDS under it.

# Current:
# ID 17:  Christian/Latter-day Saints  (parent=2)
#   ID 168: Christian/Latter-day Saints/LDS  (parent=17)  ← this is the L3 "tradition" level
#     ID 456: Christian/Latter-day Saints/LDS/LDS  (parent=168)  ← this is the L4 "denomination" level
#   ID 167: Christian/Latter-day Saints/Community of Christ  (parent=17) — already moved under Other LDS

# Wait no, ID 167 was already moved under Other LDS (ID 457). Let me re-check.

# Let me just read the current state
print("\n  Current full state:")
c.execute("""
    SELECT id, parent_id, name, full_path
    FROM taxonomy
    WHERE id IN (17, 167, 168, 456, 457, 458)
    ORDER BY id
""")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"    ID {r[0]}: parent={r[1]}, name='{r[2]}', path={r[3]}, churches={c.fetchone()[0]}")

# OK here's the current state after our earlier changes:
# ID 17: parent=2, Christian/Latter-day Saints (L2)
# ID 167: parent=457, Christian/Latter-day Saints/Other LDS/Community of Christ (too deep!)
# ID 168: parent=17, Christian/Latter-day Saints/LDS (L3)
# ID 456: parent=168, Christian/Latter-day Saints/LDS/LDS (L4)
# ID 457: parent=17, Christian/Latter-day Saints/Other LDS (L3)  
# ID 458: parent=457, Christian/Latter-day Saints/Other LDS/FLDS (L4)

# After moving parent 17 to Other, the paths become:
# ID 17: Christian/Other/Latter-day Saints (L3 - tradition!)
# ID 168: Christian/Other/Latter-day Saints/LDS (L4 - denomination!)
# ID 456: Christian/Other/Latter-day Saints/LDS/LDS (5 levels - needs fixing)
# ID 457: Christian/Other/Latter-day Saints/Other LDS (L4)
# ID 458: Christian/Other/Latter-day Saints/Other LDS/FLDS (5 levels - needs fixing)
# ID 167: Christian/Other/Latter-day Saints/Other LDS/Community of Christ (5 levels - needs fixing)

# Issues:
# 1. ID 456 (LDS/LDS) - redundant, the two LDS levels should collapse
# 2. ID 457 (Other LDS) - should be L3 tradition level, not L4
# 3. ID 458 (FLDS) and 167 (Community of Christ) should be L4 under Other LDS

# Fix: 
# - ID 168 stays as Christian/Other/Latter-day Saints/LDS (L4 denomination for mainline)
# - ID 456 children (none) could be merged into 168
# - ID 457: Christian/Other/Latter-day Saints/Other LDS → keep as L4, rename to just "Other"
#   Actually, the problem is L3 should be "Latter-day Saints" and L4 should be denomination.
#   So the structure should be:
#   Christian/Other (L2) / Latter-day Saints (L3) / LDS (L4) ← mainline
#   Christian/Other (L2) / Latter-day Saints (L3) / Community of Christ (L4)
#   Christian/Other (L2) / Latter-day Saints (L3) / FLDS (L4)
#   
#   Since 168 is "LDS" and 167 is "Community of Christ" and they're at the same level,
#   they should both be L4 under Latter-day Saints.
#
# Fix plan:
# 1. ID 17: parent=other_id, path=Christian/Other/Latter-day Saints (L3) ✓
# 2. ID 168: path=Christian/Other/Latter-day Saints/LDS (L4) → re-parent to 17 if needed
#    Actually, parent of 168 IS already 17. So path auto-fixes to Christian/Other/Latter-day Saints/LDS
# 3. ID 167: parent should be 17 (not 457), path=Christian/Other/Latter-day Saints/Community of Christ
# 4. ID 456: merge into 168 (reassign all churches), delete 456
# 5. ID 457: rename to "Other" or delete and reassign churches to 17-level
# 6. ID 458: parent=17, path=Christian/Other/Latter-day Saints/FLDS

# Let me also update all descendants' full_path
def update_paths(c, parent_id, new_base):
    """Recursively update full_path for all children of parent_id"""
    c.execute("SELECT id, name FROM taxonomy WHERE parent_id = ?", (parent_id,))
    children = c.fetchall()
    for child_id, name in children:
        new_path = f"{new_base}/{name}"
        c.execute("UPDATE taxonomy SET full_path = ? WHERE id = ?", (new_path, child_id))
        # Recurse
        update_paths(c, child_id, new_path)

update_paths(c, 17, "Christian/Other/Latter-day Saints")
print("  Updated all LDS descendant paths")

# Fix ID 456 (LDS/LDS) - merge into 168
c.execute("UPDATE churches SET taxonomy_id = 168 WHERE taxonomy_id = 456")
print(f"  Merged ID 456 churches → ID 168: {c.rowcount} records")

# Fix ID 167 - reparent to 17
c.execute("UPDATE taxonomy SET parent_id = 17, full_path = 'Christian/Other/Latter-day Saints/Community of Christ' WHERE id = 167")
print("  Reparented Community of Christ (167) directly under Latter-day Saints")

# Fix ID 458 - reparent to 17
c.execute("UPDATE taxonomy SET parent_id = 17, full_path = 'Christian/Other/Latter-day Saints/FLDS' WHERE id = 458")
print("  Reparented FLDS (458) directly under Latter-day Saints")

# Fix ID 457 - reparent to 17, rename to "Other"
c.execute("""
    UPDATE taxonomy SET parent_id = 17, name = 'Other', full_path = 'Christian/Other/Latter-day Saints/Other'
    WHERE id = 457
""")
print("  Updated Other LDS (457) to just 'Other' under Latter-day Saints")
# Move any churches at 457 to 17-level
c.execute("UPDATE churches SET taxonomy_id = 17 WHERE taxonomy_id = 457")
print(f"  Moved ID 457 churches → ID 17: {c.rowcount}")

# Step 3: Move Jehovah's Witnesses under Other
print("\n=== Step 3: Moving Jehovah's Witnesses under Other ===")
c.execute("UPDATE taxonomy SET parent_id = ?, full_path = 'Christian/Other/Jehovah''s Witnesses' WHERE id = 16", (other_id,))
print("  Moved ID 16 → Christian/Other/Jehovah's Witnesses")

update_paths(c, 16, "Christian/Other/Jehovah's Witnesses")
print("  Updated all JW descendant paths")

# Step 4: Update church records' legacy/tradition/denomination
print("\n=== Step 4: Updating church columns ===")

# LDS mainline: legacy='Other', tradition='Latter-day Saints'
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Latter-day Saints'
    WHERE taxonomy_id = 168 AND (legacy != 'Other' OR tradition != 'Latter-day Saints')
""")
print(f"  LDS mainline (tax=168): {c.rowcount} records → legacy=Other, tradition=Latter-day Saints")

# LDS Community of Christ
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Latter-day Saints', denomination = 'Community of Christ'
    WHERE taxonomy_id = 167 AND (legacy != 'Other' OR denomination != 'Community of Christ')
""")
print(f"  Community of Christ (tax=167): {c.rowcount} records → legacy=Other")

# LDS FLDS
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Latter-day Saints', denomination = 'FLDS'
    WHERE taxonomy_id = 458 AND (legacy != 'Other' OR denomination != 'FLDS')
""")
print(f"  FLDS (tax=458): {c.rowcount} records → legacy=Other")

# JW at taxonomy 16 (Christian/Other/Jehovah's Witnesses)
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Jehovah''s Witnesses'
    WHERE taxonomy_id = 16 AND (legacy != 'Other' OR tradition != 'Jehovah''s Witnesses')
""")
print(f"  JW (tax=16): {c.rowcount} records → legacy=Other, tradition=Jehovah's Witnesses")

# JW at taxonomy 165 (Christian/Other/Jehovah's Witnesses/Jehovah's Witnesses)
c.execute("""
    UPDATE churches SET legacy = 'Other', tradition = 'Jehovah''s Witnesses'
    WHERE taxonomy_id = 165 AND (legacy != 'Other' OR tradition != 'Jehovah''s Witnesses')
""")
print(f"  JW (tax=165): {c.rowcount} records → legacy=Other, tradition=Jehovah's Witnesses")

# Also fix JW misclassifications - those at wrong taxonomy IDs
c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Jehovah%Witness%' OR name LIKE '%Kingdom Hall%' OR tradition = 'jehovahs_witness')
      AND taxonomy_id NOT IN (16, 165)
""")
misclassified_jw = c.fetchone()[0]
if misclassified_jw > 0:
    # Set them to JW taxonomy + legacy/tradition
    c.execute("""
        UPDATE churches SET taxonomy_id = 165, legacy = 'Other', tradition = 'Jehovah''s Witnesses'
        WHERE (name LIKE '%Jehovah%Witness%' OR name LIKE '%Kingdom Hall%' OR tradition = 'jehovahs_witness')
          AND taxonomy_id NOT IN (16, 165)
    """)
    print(f"  Fixed {c.rowcount} misclassified JW records → tax=165, legacy=Other")

db.commit()

# Clean up: delete orphaned ID 456
c.execute("DELETE FROM taxonomy WHERE id = 456")
print("\nCleaned up orphaned taxonomy ID 456")

# Final verification
print("\n=== FINAL VERIFICATION ===")
c.execute("""
    SELECT id, parent_id, name, full_path
    FROM taxonomy
    WHERE full_path LIKE '%Latter-day Saints%' OR full_path LIKE '%Jehovah%'
    ORDER BY full_path
""")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]}: {r[3]:65s} — {c.fetchone()[0]:>6,} churches")

print(f"\nTotal time: {time.time()-start:.1f}s")
db.close()
print("Done!")

"""
Fix: Pagan/Bahai→Other, Sikh→top-level root
"""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# ============================================================
# Step 0: Clean unused duplicate taxonomy entries (IDs >= 555 with 0 refs)
# ============================================================
c.execute("""
    SELECT id, full_path FROM taxonomy WHERE id >= 555
    AND NOT EXISTS (SELECT 1 FROM churches WHERE taxonomy_id = taxonomy.id)
    ORDER BY id DESC
""")
to_del = c.fetchall()
print(f"Cleaning {len(to_del)} unused taxonomy entries:")
for r in to_del:
    print(f"  DELETE id={r[0]} {r[1]}")
    c.execute("DELETE FROM taxonomy WHERE id=?", (r[0],))
db.commit()

# ============================================================
# Step 1: Pagan → faith='Other'
# ============================================================
print("\n=== Pagan → Other ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Pagan'")
print(f"Faith=Pagan: {c.fetchone()[0]:,}")
c.execute("UPDATE churches SET faith='Other' WHERE faith='Pagan'")
print(f"  Moved: {c.rowcount}")
db.commit()

# ============================================================
# Step 2: Baháʼí → faith='Other'
# ============================================================
print("\n=== Baháʼí → Other ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Baháʼí'")
print(f"Faith=Baháʼí: {c.fetchone()[0]:,}")
c.execute("UPDATE churches SET faith='Other' WHERE faith='Baháʼí'")
print(f"  Moved: {c.rowcount}")
db.commit()

# ============================================================
# Step 3: Sikh → top-level root
# ============================================================
print("\n=== Sikh → top-level root ===")

# 3a. Change parent of Sikh taxonomy (id=55) from Other(6) to NULL
c.execute("UPDATE taxonomy SET parent_id=NULL, full_path='Sikh' WHERE id=55")
print(f"  Root node updated (id=55).")

# 3b. Update sub-path for Sikh children
# Need to walk the tree under id=55 and update all full_paths
c.execute("UPDATE taxonomy SET full_path='Sikh/Sikh' WHERE id=56")  # Sikhism -> Sikh/Sikh
print(f"  id=56 Sikhism path updated.")

# 3c. Any other children of id=55? Let me check
c.execute("SELECT id, name, full_path FROM taxonomy WHERE parent_id=55")
children = c.fetchall()
if children:
    for r in children:
        new_path = f"Sikh/{r[1]}"
        c.execute("UPDATE taxonomy SET full_path=? WHERE id=?", (new_path, r[0]))
        print(f"  id={r[0]} {r[1]} → {new_path}")
    
    # 3d. Update grandchildren (children of sub-taxonomy)
    for r in children:
        c.execute("SELECT id, name, full_path FROM taxonomy WHERE parent_id=?", (r[0],))
        grandkids = c.fetchall()
        for g in grandkids:
            new_path = f"Sikh/{r[1]}/{g[1]}"
            c.execute("UPDATE taxonomy SET full_path=? WHERE id=?", (new_path, g[0]))
            print(f"    id={g[0]} {g[1]} → {new_path}")

db.commit()

# ============================================================
# Step 4: Update Sikh church's taxonomy_id references
# ============================================================
# Churches referencing Other/Sikh (id=55) still point to it - no change needed since 
# id=55 is now a root. But churches referencing Other/Sikhism (id=56) need new path.
# Other/Sikhism (id=56) was a sibling of Sikh under Other, let me check if any churches use it
c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=56")
if c.fetchone()[0] > 0:
    print(f"\n  Warning: {c.fetchone()[0]} churches reference id=56 (old Sikhism)")
else:
    print(f"\n  0 churches reference id=56 - OK")

# ============================================================
# Step 5: Delete other unused Sikh entries (Now id=55 is root, id=56 Sikhism is orphaned)  
# Actually id=56 (Sikhism) is a separate path, not a child of id=55. Let me check.
# id=55 parent_id=6 (Other), name='Sikh', full_path='Other/Sikh'
# id=56 parent_id=6 (Other), name='Sikhism', full_path='Other/Sikhism'
# They're siblings under Other. Now id=55 is root, id=56 is orphaned under Other.
# Since 0 churches reference id=56, I can delete it.
c.execute("DELETE FROM taxonomy WHERE id=56")
print(f"  Deleted orphaned id=56 (Sikhism)")
db.commit()

# ============================================================
# VERIFY
# ============================================================
print("\n=== Verification ===")
c.execute("SELECT id, parent_id, name, full_path FROM taxonomy WHERE full_path LIKE '%Sikh%' OR id=55")
for r in c.fetchall():
    print(f"  id={r[0]:3d} parent={str(r[1]):5s} {r[2]:25s} {r[3]}")

print("\nFaith counts after changes:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>8,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"  {'NULL':20s} {c.fetchone()[0]:>8,}")

db.close()
print("\nDone!")

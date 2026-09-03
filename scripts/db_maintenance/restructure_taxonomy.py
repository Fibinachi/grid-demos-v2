"""
Comprehensive taxonomy restructure:
  Abrahamic: Christian, Islam, Judaism
  Dharmic:   Hindu, Buddhist, Sikh, Jain
  Taoic:     Shinto, Taoist, Confucian
  Other:     Pagan, Bahai, everything else

Also: Pagan/Bahai -> faith=Other
"""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

def log(msg):
    print(msg)

def reparent_tree(tax_id, new_parent_id, new_prefix):
    """Recursively reparent a taxonomy node and update all descendants' full_paths."""
    c.execute("SELECT name, full_path FROM taxonomy WHERE id=?", (tax_id,))
    row = c.fetchone()
    if not row:
        return
    name, old_path = row
    c.execute("UPDATE taxonomy SET parent_id=? WHERE id=?", (new_parent_id, tax_id))
    new_path = f"{new_prefix}/{name}" if new_prefix else name
    c.execute("UPDATE taxonomy SET full_path=? WHERE id=?", (new_path, tax_id))
    log(f"  {old_path:45s} -> {new_path}")
    c.execute("SELECT id, name FROM taxonomy WHERE parent_id=?", (tax_id,))
    for child_id, child_name in c.fetchall():
        reparent_tree(child_id, tax_id, new_path)

# ============================================================
# Step 0: Clean unused duplicate taxonomy entries
# ============================================================
log("=== Clean duplicate taxonomy entries ===")
c.execute("""
    SELECT id, full_path FROM taxonomy WHERE id >= 555
    AND NOT EXISTS (SELECT 1 FROM churches WHERE taxonomy_id = taxonomy.id)
    ORDER BY id DESC
""")
to_del = c.fetchall()
for r in to_del:
    log(f"  DEL id={r[0]} {r[1]}")
    c.execute("DELETE FROM taxonomy WHERE id=?", (r[0],))
db.commit()

# Clean orphan sub-entries
for orphan in [47, 56, 561, 562, 563, 564]:
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=?", (orphan,))
    if c.fetchone()[0] == 0:
        c.execute("SELECT COUNT(*) FROM taxonomy WHERE id=?", (orphan,))
        if c.fetchone()[0]:
            c.execute("DELETE FROM taxonomy WHERE id=?", (orphan,))
            log(f"  DEL orphan id={orphan}")
db.commit()

# ============================================================
# Step 1: Create umbrella root nodes
# ============================================================
log("\n=== Create umbrella roots ===")
c.execute("SELECT COALESCE(MAX(id), 600) + 1 FROM taxonomy")
next_id = c.fetchone()[0]

roots = {
    'Abrahamic': next_id,
    'Dharmic': next_id + 1,
    'Taoic': next_id + 2,
}
for name, rid in roots.items():
    c.execute("INSERT INTO taxonomy (id, parent_id, name, full_path) VALUES (?, NULL, ?, ?)", (rid, name, name))
    log(f"  Created: id={rid} {name}")
db.commit()

# ============================================================
# Step 2: Rehome faiths under umbrella roots
# ============================================================
log("\n=== Rehome faiths ===")
moves = [
    (2, roots['Abrahamic'], 'Abrahamic'),
    (4, roots['Abrahamic'], 'Abrahamic'),
    (5, roots['Abrahamic'], 'Abrahamic'),
    (3, roots['Dharmic'],   'Dharmic'),
    (1, roots['Dharmic'],   'Dharmic'),
    (55, roots['Dharmic'],  'Dharmic'),
    (46, roots['Dharmic'],  'Dharmic'),
    (7, roots['Taoic'],     'Taoic'),
    (59, roots['Taoic'],    'Taoic'),
    (45, roots['Taoic'],    'Taoic'),
]
for tax_id, new_parent, prefix in moves:
    reparent_tree(tax_id, new_parent, prefix)
db.commit()

# ============================================================
# Step 3: Update faith values on churches
# ============================================================
log("\n=== Update faith values ===")
mapping = {
    'Hindu': 'Dharmic', 'Buddhist': 'Dharmic',
    'Sikh': 'Dharmic',
    'Shinto': 'Taoic', 'Taoist': 'Taoic',
    'Christian': 'Abrahamic', 'Islam': 'Abrahamic', 'Judaism': 'Abrahamic',
}
for old_faith, new_faith in mapping.items():
    c.execute("UPDATE churches SET faith=? WHERE faith=?", (new_faith, old_faith))
    log(f"  {old_faith:15s} -> {new_faith:15s}: {c.rowcount:>8,}")
db.commit()

# ============================================================
# Step 4: Pagan/Bahai -> faith='Other'
# ============================================================
log("\n=== Pagan & Bahai -> Other ===")
for f in ['Pagan', 'Bahai', 'Bahai']:
    # Try exact match first
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,))
    cnt = c.fetchone()[0]
    if cnt:
        c.execute("UPDATE churches SET faith='Other' WHERE faith=?", (f,))
        log(f"  {f}: {cnt} -> Other")

# Also handle any straggler faith values with Bahai in the name
c.execute("UPDATE churches SET faith='Other' WHERE faith LIKE '%Bah%'")
if c.rowcount:
    log(f"  Bahai-like -> Other: {c.rowcount}")

# Make sure Confucian taxonomies have Taoic faith
c.execute("""
    UPDATE churches SET faith='Taoic'
    WHERE taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path LIKE '%Confucian%')
    AND faith != 'Taoic'
""")
if c.rowcount:
    log(f"  Confucian faith fix: {c.rowcount}")

db.commit()

# ============================================================
# VERIFICATION
# ============================================================
log("\n=== Root-level taxonomy ===")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE parent_id IS NULL ORDER BY id")
for r in c.fetchall():
    c.execute("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM taxonomy WHERE id=?
            UNION ALL
            SELECT t.id FROM taxonomy t JOIN subtree s ON t.parent_id=s.id
        )
        SELECT COUNT(*) FROM churches WHERE taxonomy_id IN (SELECT id FROM subtree)
    """, (r[0],))
    log(f"  id={r[0]:3d} {r[1]:20s} churches: {c.fetchone()[0]:>8,}")

print("\nFaith counts:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>8,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"  {'NULL':20s} {c.fetchone()[0]:>8,}")

log("\n=== Tree structure (level 1-2) ===")
c.execute("""
    SELECT t1.full_path FROM taxonomy t1
    WHERE t1.parent_id IS NULL
    UNION ALL
    SELECT t2.full_path FROM taxonomy t2
    WHERE t2.parent_id IN (SELECT id FROM taxonomy WHERE parent_id IS NULL)
    ORDER BY full_path
""")
for r in c.fetchall():
    log(f"  {r[0]}")

db.close()
log("\nDone!")

"""
Phase 4: Assign faith values to NULL-faith records from their taxonomy_id.
Then set FLTD for the newly assigned faiths (Taoist, Chinese Folk).
"""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

def progress(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ============================================================
# Step 1: Build root-to-faith mapping from taxonomy table
# ============================================================
progress("Building root->faith map...")
c.execute("SELECT id, name FROM taxonomy WHERE parent_id IS NULL")
root_to_faith = {r[0]: r[1] for r in c.fetchall()}
# Map root parent to the faith value
# Some roots have slightly different paths, let's also match sub-trees
# The taxonomy parent_id forms a tree. For any taxonomy ID, we need to find its root.
# Approach: build a lookup of id->parent_id and traverse up.
c.execute("SELECT id, parent_id FROM taxonomy")
all_parents = dict(c.fetchall())

def find_root(tax_id):
    """Walk up the taxonomy tree to find the root node."""
    seen = set()
    while tax_id in all_parents and all_parents[tax_id] is not None:
        if tax_id in seen:
            break
        seen.add(tax_id)
        tax_id = all_parents[tax_id]
    return tax_id

# Map taxonomy ID -> faith
tax_to_faith = {}
for tid in all_parents:
    root = find_root(tid)
    tf = root_to_faith.get(root)
    if tf:
        tax_to_faith[tid] = tf
progress(f"  Mapped {len(tax_to_faith)} taxonomy IDs to faiths")

# Also handle special cases
tax_to_faith.update({
    44: 'Other',  # Chinese Folk (under Other)
    48: 'Other',  # Local Spiritual Assembly (Bahai)
    49: 'Other',  # Masonic
    50: 'Other',  # National Spiritual Assembly (Bahai)
    51: 'Other',  # Non-religious
    52: 'Other',  # Other/Other
    54: 'Other',  # Rastafarian
    57: 'Other',  # Spiral Cult
    58: 'Other',  # Taoism
    59: 'Other',  # Taoist
    60: 'Other',  # Unknown
    61: 'Other',  # Zoroastrian
    62: 'Other',  # unclassified
})

# ============================================================
# Step 2: Assign faith from taxonomy_id for NULL faith records
# ============================================================
progress("\nAssigning faith from taxonomy_id...")

# Process each root faith
import sqlite3
for root_id, faith_name in root_to_faith.items():
    # Get all taxonomy IDs under this root
    c.execute("""
        WITH RECURSIVE subtree AS (
            SELECT id FROM taxonomy WHERE id = ?
            UNION ALL
            SELECT t.id FROM taxonomy t JOIN subtree s ON t.parent_id = s.id
        )
        SELECT id FROM subtree
    """, (root_id,))
    tax_ids = [r[0] for r in c.fetchall()]
    
    if not tax_ids:
        continue
    
    # Build a big OR condition
    placeholders = ','.join(['?'] * len(tax_ids))
    sql = f"UPDATE churches SET faith=? WHERE (faith IS NULL OR faith='') AND taxonomy_id IN ({placeholders})"
    c.execute(sql, [faith_name] + tax_ids)
    progress(f"  {faith_name:15s}: {c.rowcount:>7,}")

# Also check taxonomy IDs that don't have a root parent (orphans)
c.execute("""
    SELECT c.taxonomy_id, COUNT(*) FROM churches c
    LEFT JOIN taxonomy t ON c.taxonomy_id = t.id
    WHERE (c.faith IS NULL OR c.faith='') AND c.taxonomy_id IS NOT NULL
      AND c.taxonomy_id NOT IN ({})
    GROUP BY c.taxonomy_id
    ORDER BY COUNT(*) DESC LIMIT 5
""".format(','.join(map(str, tax_to_faith.keys()))))
remaining = c.fetchall()
if remaining:
    progress("\nUnmapped taxonomy IDs:")
    for r in remaining:
        progress(f"  tax_id={r[0]}: {r[1]:,} records")

db.commit()

# ============================================================
# Step 3: Set FLTD for newly assigned faiths
# ============================================================
progress("\n=== Setting FLTD for newly assigned faiths ===")

# Taoist (faith='Taoist', Other/Taoist taxonomy -> Other/Taoist)
c.execute("UPDATE churches SET legacy='Taoist', tradition='Taoist' WHERE faith='Taoist' AND (legacy IS NULL OR legacy='')")
progress(f"  Taoist → Taoist: {c.rowcount:,}")

# Chinese Folk (Other/Chinese Folk)
c.execute("UPDATE churches SET legacy='Other', tradition='Chinese Folk' WHERE faith='Other' AND taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path='Other/Chinese Folk') AND (legacy IS NULL OR legacy='')")
progress(f"  Chinese Folk: {c.rowcount:,}")

# Other/Taoist taxonomy -> Taoist faith (if taxonomy says Taoist but faith was NULL)
c.execute("""
    UPDATE churches SET faith='Taoist', legacy='Taoist', tradition='Taoist'
    WHERE (faith IS NULL OR faith='') 
    AND taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path LIKE '%Taoist%' OR full_path LIKE '%Taoism%')
""")
progress(f"  NULL+Taoist tax→Taoist: {c.rowcount:,}")

# Chinese Folk taxonomy -> Other faith
c.execute("""
    UPDATE churches SET faith='Other', legacy='Other', tradition='Chinese Folk'
    WHERE (faith IS NULL OR faith='') 
    AND taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path='Other/Chinese Folk')
""")
progress(f"  NULL+Chinese Folk→Other: {c.rowcount:,}")

# Unknown taxonomy -> set legacy
c.execute("""
    UPDATE churches SET legacy='Other', tradition='Unknown'
    WHERE faith='Other' AND taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path='Other/Unknown') 
    AND (legacy IS NULL OR legacy='')
""")
progress(f"  Other/Unknown→Other/Unknown: {c.rowcount:,}")

db.commit()

# ============================================================
# Step 4: Handle remaining NULL faith records 
# ============================================================
progress("\n=== Remaining NULL faith ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
remaining = c.fetchone()[0]
progress(f"Total NULL faith remaining: {remaining:,}")

if remaining:
    c.execute("""
        SELECT COALESCE(t.full_path, 'NO TAX') as fp, COUNT(*) FROM churches c
        LEFT JOIN taxonomy t ON c.taxonomy_id = t.id
        WHERE c.faith IS NULL OR c.faith = ''
        GROUP BY fp ORDER BY COUNT(*) DESC LIMIT 10
    """)
    progress("By taxonomy:")
    for r in c.fetchall():
        progress(f"  {str(r[0]):50s} {r[1]:>8,}")

# ============================================================
# SUMMARY
# ============================================================
progress("\n=== FINAL FAITH COUNTS ===")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>8,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"  {'NULL':20s} {c.fetchone()[0]:>8,}")

db.close()
progress("\nPhase 4 complete!")

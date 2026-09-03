import sqlite3
db = sqlite3.connect("churches.db")
c = db.cursor()

print("=== Cathedral entries status ===")
c.execute("SELECT parent_cath_type, relationship, COUNT(*) FROM catholic_hierarchy WHERE cath_type='cathedral' GROUP BY parent_cath_type, relationship")
for r in c.fetchall():
    print(f"  parent_cath_type={r[0] or 'NULL':15s} relationship={r[1] or 'NULL':15s} count={r[2]}")

print()
print("=== Dioceses with/without cathedral ===")
c.execute("SELECT COUNT(DISTINCT parent_id) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NOT NULL")
print(f"  Dioceses with cathedral child: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
total = c.fetchone()[0]
print(f"  Total dioceses/archdioceses: {total}")

# How many cathedrals still have parent_id NULL?
c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NULL")
print(f"\n  Cathedrals still w/o parent: {c.fetchone()[0]}")

# And total with parent
c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type='cathedral' AND parent_id IS NOT NULL")
print(f"  Cathedrals WITH parent: {c.fetchone()[0]}")

# What's NOT been linked?
print()
print("=== All hierarchy entries that are 'cathedral' or linked to a cathedral church ===")
c.execute("""
    SELECT ch.cath_type, 
           CASE WHEN ch.parent_id IS NOT NULL THEN 'linked' ELSE 'orphan' END,
           COUNT(*)
    FROM catholic_hierarchy ch
    WHERE ch.cath_type = 'cathedral'
       OR ch.church_id IN (
           SELECT id FROM churches WHERE landmark_type='cathedral' AND legacy='Catholic'
       )
    GROUP BY ch.cath_type, 
           CASE WHEN ch.parent_id IS NOT NULL THEN 'linked' ELSE 'orphan' END
    ORDER BY ch.cath_type
""")
for r in c.fetchall():
    print(f"  cath_type={r[0]:15s} {r[1]:8s} count={r[2]}")

db.close()

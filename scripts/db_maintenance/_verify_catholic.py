"""Verify Catholic hierarchy and FTLD results."""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')

print('=== FTLD VERIFICATION ===')
for q, l in [
    ("SELECT COUNT(*) FROM churches WHERE faith='christian' AND legacy='Catholic'", "faith=christian + legacy=Catholic"),
    ("SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND tradition='Catholic Churches'", "legacy=Catholic + tradition=Catholic Churches"),
    ("SELECT COUNT(*) FROM churches WHERE legacy='Catholic' AND (tradition IS NULL OR tradition='')", "legacy=Catholic but tradition missing"),
    ("SELECT COUNT(*) FROM churches WHERE tradition LIKE '%Catholic%' AND (legacy IS NULL OR legacy='')", "tradition LIKE Catholic but legacy missing"),
]:
    c = db.execute(q).fetchone()[0]
    print(f'  {l}: {c:,}')

print('\n=== CATHOLIC HIERARCHY ===')
total = db.execute("SELECT COUNT(*) FROM catholic_hierarchy").fetchone()[0]
print(f'  Total: {total:,}')

print('\nType breakdown:')
for r in db.execute("SELECT cath_type, COUNT(*) FROM catholic_hierarchy GROUP BY cath_type ORDER BY COUNT(*) DESC"):
    print(f'  {r[1]:>8,} | {r[0]}')

linked = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
print(f'\n  Linked: {linked:,}')
print(f'  Top-level: {total-linked:,}')

print('\nDepth from Holy See:')
for r in db.execute("""
    WITH RECURSIVE depth AS (
        SELECT id, 0 AS lvl FROM catholic_hierarchy WHERE cath_type='holy_see'
        UNION ALL
        SELECT ch.id, d.lvl+1 FROM catholic_hierarchy ch 
        JOIN depth d ON ch.parent_id = d.id
    )
    SELECT lvl, COUNT(*) FROM depth GROUP BY lvl ORDER BY lvl
"""):
    print(f'  Level {r[0]}: {r[1]:,}')

print('\nProvenance:')
for r in db.execute("SELECT source, status, churches_updated, churches_inserted FROM provenance_log WHERE source LIKE 'catholic%' ORDER BY rowid DESC"):
    print(f'  {r[0]}: status={r[1]}, updated={r[2]}, inserted={r[3]}')

db.close()

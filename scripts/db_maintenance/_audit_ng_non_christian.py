"""Audit and fix ALL non-Christian/non-Muslim misclassifications in Nigeria."""
import sqlite3
db = sqlite3.connect('e:/grid/churches.db')
db.row_factory = sqlite3.Row

print('='*60)
print('AUDIT: All non-Christian, non-Islam, non-Other entries in Nigeria')
print('='*60)

for faith in ['Buddhist', 'Judaism', 'Sikh', 'Shinto', 'Other']:
    print(f'\n=== {faith} in NG ===')
    for r in db.execute("""
        SELECT taxonomy_id, COUNT(*) n, GROUP_CONCAT(DISTINCT landmark_type) as types
        FROM churches WHERE country='NG' AND faith=?
        GROUP BY taxonomy_id ORDER BY n DESC
    """, [faith]):
        print(f'  tax_id={r["taxonomy_id"]}: {r["n"]} entries | types={r["types"]}')
    
    # Sample
    for r in db.execute("""
        SELECT id, name, landmark_type, taxonomy_id, source, state
        FROM churches WHERE country='NG' AND faith=?
        LIMIT 10
    """, [faith]):
        print(f'  [{r["id"]}] {r["name"][:60]:<62} type={r["landmark_type"]:<12} tax={r["taxonomy_id"]} state={r["state"]} src={r["source"]}')

# Also check taxonomy names
print('\n=== Taxonomy ID lookup ===')
tax_ids = set()
for r in db.execute("SELECT DISTINCT taxonomy_id FROM churches WHERE country='NG' AND faith NOT IN ('Christian','Islam')"):
    tax_ids.add(r[0])
print(f'Unique taxonomy IDs in non-Christian/Islam NG: {sorted(tax_ids)}')
for tid in sorted(tax_ids):
    name = db.execute("SELECT name FROM taxonomy WHERE id=?", [tid]).fetchone()
    if name:
        print(f'  {tid}: {name[0]}')
    else:
        print(f'  {tid}: (not found)')

db.close()

"""Check exact SA gaps."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

hier = set(r[0] for r in db.execute("SELECT church_id FROM sa_hierarchy WHERE church_id IS NOT NULL").fetchall())
print(f'sa_hierarchy: {len(hier)} entries')

name_sql = """
    SELECT id FROM churches
    WHERE name LIKE '%Salvation Army%'
       OR name LIKE '%Arm\u00e9e du Salut%'
       OR name LIKE '%Heilsarmee%'
       OR name LIKE '%Frelsesarmeen%'
       OR name LIKE '%Pelastusarmeija%'
       OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
       OR name LIKE '%Ejercito de Salvacion%'
       OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%'
       OR name LIKE '%Exercito de Salvacao%'
       OR name LIKE '%Armia Zbawienia%'
       OR name LIKE '%Fr\u00e4lsningsarm\u00e9n%'
       OR name LIKE '%Fralsningsarmen%'
"""
by_name = set(r[0] for r in db.execute(name_sql).fetchall())
print(f'By name (all patterns): {len(by_name)}')

by_denom = set(r[0] for r in db.execute("SELECT id FROM churches WHERE denomination_affiliation LIKE '%Salvation Army%'").fetchall())
print(f'By denom: {len(by_denom)}')

combined = by_name | by_denom
print(f'Combined: {len(combined)}')

missing = {x for x in combined if x is not None} - {x for x in hier if x is not None}
print(f'\nMissing from hierarchy: {len(missing)}')
if missing:
    for mid in sorted(missing):
        r = db.execute("SELECT id, name, city, country, denomination_affiliation, source FROM churches WHERE id=?", (mid,)).fetchone()
        if r:
            print(f'  {r[0]} | {str(r[1] or "")[:55]} | {str(r[2] or "")[:20]} | {r[3]} | denom={str(r[4] or "")[:25]} | {r[5]}')

# Additional checks
cnt = db.execute("SELECT COUNT(*) FROM churches WHERE denomination_affiliation='The Salvation Army'").fetchone()[0]
print(f'\nChurches with SA denom: {cnt}')
cnt2 = db.execute("SELECT COUNT(*) FROM churches WHERE subtradition='Salvationist'").fetchone()[0]
print(f'Churches with subtradition=Salvationist: {cnt2}')

# Check what was updated vs what's in hierarchy
updated = set(r[0] for r in db.execute("SELECT id FROM churches WHERE denomination_affiliation='The Salvation Army'").fetchall())
print(f'\nUpdated with SA denom: {len(updated)}')
not_in_hier = updated - hier
print(f'Updated but NOT in hierarchy: {len(not_in_hier)}')
if not_in_hier:
    for mid in sorted(list(not_in_hier)[:10]):
        r = db.execute("SELECT id, name, city, source FROM churches WHERE id=?", (mid,)).fetchone()
        if r:
            print(f'  {r[0]} | {str(r[1] or "")[:55]} | {str(r[2] or "")[:20]} | {r[3]}')

db.close()

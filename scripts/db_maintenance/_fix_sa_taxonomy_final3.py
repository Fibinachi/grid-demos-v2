"""Complete SA taxonomy fix for ALL entries."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)
db.execute('PRAGMA busy_timeout=30000')

ids = [r[0] for r in db.execute("""
    SELECT id FROM churches
    WHERE name LIKE '%Salvation Army%'
       OR name LIKE '%Ejercito de Salvacion%'
       OR name LIKE '%Exercito de Salvacao%'
       OR name LIKE '%Arm\u00e9e du Salut%'
       OR name LIKE '%Heilsarmee%'
       OR name LIKE '%Frelsesarmeen%'
       OR name LIKE '%Pelastusarmeija%'
       OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
       OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%'
       OR name LIKE '%Fr\u00e4lsningsarm\u00e9n%'
       OR name LIKE '%Fralsningsarmen%'
       OR name LIKE '%Armia Zbawienia%'
    ORDER BY id
""").fetchall()]

total = len(ids)
print(f'Total SA entries: {total}')

updated = 0
for cid in ids:
    db.execute("""
        UPDATE churches
        SET faith = 'christian',
            legacy = 'Protestant',
            tradition = 'Holiness Churches',
            denomination = 'Salvation Army'
        WHERE id = ?
    """, (cid,))
    updated += 1
    if updated % 200 == 0:
        db.commit()
        print(f'  {updated}/{total}')

db.commit()
print(f'Done: {updated} updated')

# Verify
c = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Salvation Army%' OR name LIKE '%Ejercito de Salvacion%')
      AND faith = 'christian'
      AND legacy = 'Protestant'
      AND tradition = 'Holiness Churches'
      AND denomination = 'Salvation Army'
""").fetchone()[0]
print(f'With full correct taxonomy: {c:,}')

# Any remaining with wrong taxonomy?
wrong = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Salvation Army%' OR name LIKE '%Ejercito de Salvacion%'
           OR name LIKE '%Exercito de Salvacao%' OR name LIKE '%Arm\u00e9e du Salut%'
           OR name LIKE '%Heilsarmee%' OR name LIKE '%Frelsesarmeen%'
           OR name LIKE '%Pelastusarmeija%' OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
           OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%' OR name LIKE '%Fr\u00e4lsningsarm\u00e9n%'
           OR name LIKE '%Fralsningsarmen%' OR name LIKE '%Armia Zbawienia%')
      AND NOT (faith = 'christian' AND legacy = 'Protestant'
               AND tradition = 'Holiness Churches' AND denomination = 'Salvation Army')
""").fetchone()[0]
print(f'Remaining with wrong taxonomy: {wrong}')

db.close()

"""Bulk fix SA taxonomy - single SQL UPDATE."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

print('Running bulk UPDATE...')
db.execute("""
    UPDATE churches
    SET faith = 'christian',
        legacy = 'Protestant',
        tradition = 'Holiness Churches',
        denomination = 'Salvation Army'
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
""")
db.commit()

print(f'Rows updated: {db.execute("SELECT changes()").fetchone()[0]}')

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

wrong = db.execute("""
    SELECT COUNT(*) FROM churches
    WHERE (name LIKE '%Salvation Army%' OR name LIKE '%Ejercito de Salvacion%'
           OR name LIKE '%Arm\u00e9e du Salut%' OR name LIKE '%Heilsarmee%')
      AND NOT (faith = 'christian' AND legacy = 'Protestant'
               AND tradition = 'Holiness Churches' AND denomination = 'Salvation Army')
""").fetchone()[0]
print(f'Remaining with wrong taxonomy: {wrong}')

db.close()

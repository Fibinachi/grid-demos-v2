"""Fast batch backfill of Eastern Rite sui iuris traditions."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

# Sui iuris patterns
sui_iuris = [
    ('ukrainian', 'Ukrainian Greek Catholic'),
    ('melkite', 'Melkite Greek Catholic'),
    ('maronite', 'Maronite Catholic'),
    ('syro-malabar', 'Syro-Malabar Catholic'),
    ('syro malabar', 'Syro-Malabar Catholic'),
    ('malabar catholic', 'Syro-Malabar Catholic'),
    ('syro-malankara', 'Syro-Malankara Catholic'),
    ('syro malankara', 'Syro-Malankara Catholic'),
    ('malankara catholic', 'Syro-Malankara Catholic'),
    ('chaldean', 'Chaldean Catholic'),
    ('syriac catholic', 'Syriac Catholic'),
    ('armenian catholic', 'Armenian Catholic'),
    ('coptic catholic', 'Coptic Catholic'),
    ('ethiopian catholic', 'Ethiopian Catholic'),
    ('eritrean catholic', 'Eritrean Catholic'),
    ('byzantine catholic', 'Byzantine Catholic'),
    ('ruthenian', 'Ruthenian Catholic'),
    ('romanian catholic', 'Romanian Catholic'),
    ('hungarian greek', 'Hungarian Greek Catholic'),
    ('slovak greek', 'Slovak Greek Catholic'),
    ('bulgarian greek', 'Bulgarian Greek Catholic'),
    ('italo-albanian', 'Italo-Albanian Catholic'),
    ('greek catholic', 'Greek Catholic'),
    ('eastern catholic', 'Eastern Catholic'),
    ('oriental catholic', 'Eastern Catholic'),
]

total = 0
for pattern, tradition in sui_iuris:
    db.execute("""
        UPDATE churches SET tradition = ?
        WHERE legacy = 'Catholic'
          AND name LIKE ?
          AND (tradition IS NULL OR tradition = '' OR tradition = 'Catholic Churches' OR tradition = 'Catholic')
    """, (tradition, f'%{pattern}%'))
    c = db.execute("SELECT changes()").fetchone()[0]
    if c:
        total += c
        print(f'  {c:>4} | {tradition:30s} | {pattern}')

db.commit()

# Also search by denomination field
for pattern, tradition in sui_iuris:
    db.execute("""
        UPDATE churches SET tradition = ?
        WHERE legacy = 'Catholic'
          AND denomination LIKE ?
          AND (tradition IS NULL OR tradition = '' OR tradition = 'Catholic Churches' OR tradition = 'Catholic')
    """, (tradition, f'%{pattern}%'))
    c = db.execute("SELECT changes()").fetchone()[0]
    total += c

db.commit()

print(f'\nTotal updated: {total}')

# Verify
print('\nSui iuris traditions set:')
for r in db.execute("SELECT tradition, COUNT(*) FROM churches WHERE tradition IN ('Ukrainian Greek Catholic','Maronite Catholic','Byzantine Catholic','Ruthenian Catholic','Syro-Malabar Catholic','Melkite Greek Catholic','Chaldean Catholic','Greek Catholic','Syro-Malankara Catholic','Armenian Catholic','Syriac Catholic','Coptic Catholic','Romanian Catholic','Eritrean Catholic','Hungarian Greek Catholic','Slovak Greek Catholic','Bulgarian Greek Catholic','Italo-Albanian Catholic','Eastern Catholic') GROUP BY tradition ORDER BY COUNT(*) DESC"):
    print(f'  {r[1]:>4} | {r[0]}')

db.close()

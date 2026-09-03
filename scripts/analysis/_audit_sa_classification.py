"""Audit Salvation Army classification results."""
import sqlite3, sys

sys.path.insert(0, 'e:\\grid\\scripts\\db_maintenance')
from standardize_salvation_army import classify_sa_name

db = sqlite3.connect('E:\\grid\\churches.db')

cur = db.execute("""
    SELECT id, name, city, state, country
    FROM churches
    WHERE name LIKE '%Salvation Army%'
       OR name LIKE '%Arm\u00e9e du Salut%'
       OR name LIKE '%Heilsarmee%'
       OR name LIKE '%Frelsesarmeen%'
       OR name LIKE '%Pelastusarmeija%'
       OR name LIKE '%Ej\u00e9rcito de Salvaci\u00f3n%'
       OR name LIKE '%Ex\u00e9rcito de Salva\u00e7\u00e3o%'
    ORDER BY id
""")
rows = cur.fetchall()

results = {}
for r in rows:
    church_id, name, city, state, country = r
    sa_type, detail, normalized, extracted_city = classify_sa_name(name or '', city or '', country or '')
    if sa_type not in results:
        results[sa_type] = []
    results[sa_type].append((name, city, state, country, normalized, detail, extracted_city))

for sa_type in sorted(results.keys()):
    items = results[sa_type]
    print(f'\n{"="*60}')
    print(f'{sa_type.upper()} ({len(items)} entries)')
    print(f'{"="*60}')
    for name, city, state, country, normalized, detail, extracted in items[:12]:
        print(f'  Orig: {str(name or ""):55s}')
        print(f'  Norm: {str(normalized or ""):55s}')
        print(f'  City: {str(city or ""):20s} | Extracted: {str(extracted or ""):20s} | Det: {detail}')
        print()

db.close()

"""Check Salvation Army entries by denomination fields vs name."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

# 1. By name patterns (what we already have)
print("=== By NAME pattern ===")
name_sql = """
    SELECT id, name, city, country, denomination_affiliation, family
    FROM churches
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
"""
by_name = set(r[0] for r in db.execute(name_sql).fetchall())
print(f'  {len(by_name):,} entries')

# 2. By denomination_affiliation
print("\n=== By DENOMINATION_AFFILIATION ===")
for pattern in ['%Salvation Army%', '%Salvation%', '%Salut%', '%Heilsarmee%', '%Frelsesarmeen%']:
    cur = db.execute("SELECT id, name, city, denomination_affiliation FROM churches WHERE denomination_affiliation LIKE ? LIMIT 5", (pattern,))
    rows = cur.fetchall()
    cnt = db.execute("SELECT COUNT(*) FROM churches WHERE denomination_affiliation LIKE ?", (pattern,)).fetchone()[0]
    if cnt > 0:
        print(f'  {pattern:30s}: {cnt:>5} entries')
        for r in rows[:3]:
            print(f'    id={r[0]} | {str(r[1])[:50]:50s} | {str(r[2] or "")[:20]:20s} | denom={str(r[3] or "")}')

# 3. By family
print("\n=== By FAMILY ===")
for pattern in ['%Salvation%', '%Holiness%', '%Salvation Army%']:
    cnt = db.execute("SELECT COUNT(*) FROM churches WHERE family LIKE ?", (pattern,)).fetchone()[0]
    if cnt > 0:
        cur = db.execute("SELECT id, name, family FROM churches WHERE family LIKE ? LIMIT 3", (pattern,))
        for r in cur:
            print(f'  {pattern:30s}: {cnt:>5} total | id={r[0]} | {str(r[1])[:50]:50s} | family={r[2]}')

# 4. By subtradition
print("\n=== By SUBTRADITION ===")
cnt = db.execute("SELECT COUNT(*) FROM churches WHERE subtradition LIKE '%Salvation%'").fetchone()[0]
print(f'  subtradition LIKE "%Salvation%": {cnt}')
if cnt > 0:
    cur = db.execute("SELECT id, name, subtradition FROM churches WHERE subtradition LIKE '%Salvation%' LIMIT 5")
    for r in cur:
        print(f'    id={r[0]} | {str(r[1])[:50]:50s} | subtradition={r[2]}')

# 5. By religion_type
print("\n=== By RELIGION_TYPE ===")
cnt = db.execute("SELECT COUNT(*) FROM churches WHERE religion_type LIKE '%Salvation%'").fetchone()[0]
print(f'  religion_type LIKE "%Salvation%": {cnt}')

# 6. Check for entries that have SA denom but NOT in name search
denom_sql = """
    SELECT id, name, city, country, denomination_affiliation
    FROM churches
    WHERE denomination_affiliation LIKE '%Salvation Army%'
"""
by_denom = set(r[0] for r in db.execute(denom_sql).fetchall())
print(f'\n=== By denomination_affiliation (full): {len(by_denom):,} entries ===')

only_by_denom = by_denom - by_name
print(f'\nIn denomination_affiliation but NOT in name search: {len(only_by_denom):,}')
if only_by_denom:
    cur = db.execute(f"""
        SELECT id, name, city, country, denomination_affiliation
        FROM churches 
        WHERE id IN ({','.join(str(x) for x in list(only_by_denom)[:30])})
        ORDER BY name
    """)
    for r in cur:
        print(f'  {r[0]:>8} | {str(r[1] or "")[:55]:55s} | {str(r[2] or "")[:20]:20s} | {r[3]:3s} | denom={str(r[4] or "")[:30]}')
    print(f'  ... and {len(only_by_denom) - 30} more')

# 7. Combined: should search both name AND denomination
combined = by_name | by_denom
print(f'\n=== Combined unique (name OR denom): {len(combined):,} entries ===')

# 8. Check what's currently in sa_hierarchy
hier = set(r[0] for r in db.execute("SELECT church_id FROM sa_hierarchy WHERE church_id IS NOT NULL").fetchall())
print(f'\n=== Currently in sa_hierarchy: {len(hier):,} entries ===')

still_missing = combined - hier
print(f'\nStill missing from sa_hierarchy: {len(still_missing):,}')
if still_missing:
    cur = db.execute(f"""
        SELECT id, name, city, country, denomination_affiliation, source
        FROM churches 
        WHERE id IN ({','.join(str(x) for x in list(still_missing)[:20])})
        ORDER BY name
    """)
    for r in cur:
        print(f'  {r[0]:>8} | {str(r[1] or "")[:55]:55s} | {str(r[2] or "")[:20]:20s} | {r[3]:3s} | denom={str(r[4] or "")[:25]:25s} | {str(r[5] or "")}')
    print(f'  ... and {len(still_missing) - 20} more')

# 9. Check also by name containing 'Salvation' (broader than 'Salvation Army')
print('\n=== Broader: name LIKE "%Salvation%" (not just "Salvation Army") ===')
cur = db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%Salvation%' AND name NOT LIKE '%Salvation Army%'")
extra_salvation = cur.fetchone()[0]
print(f'  Name has "Salvation" but not "Salvation Army": {extra_salvation}')
if extra_salvation:
    cur = db.execute("""
        SELECT id, name, city, country, denomination_affiliation
        FROM churches 
        WHERE name LIKE '%Salvation%' AND name NOT LIKE '%Salvation Army%'
        LIMIT 15
    """)
    for r in cur:
        print(f'  {r[0]:>8} | {str(r[1] or "")[:55]:55s} | {str(r[2] or "")[:20]:20s} | {r[3]:3s} | denom={str(r[4] or "")[:30]}')

db.close()

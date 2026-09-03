"""Check if all Salvation Army entities are covered by the hierarchy."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

# 1. Full search: all possible SA name patterns
print("=== Full SA search by name pattern ===")
patterns = [
    ('Salvation Army', 'English'),
    ('Arm\u00e9e du Salut', 'French'),
    ('Heilsarmee', 'German'),
    ('Fr\u00e4lsningsarm\u00e9n', 'Swedish'),
    ('Frelsesarmeen', 'Norwegian'),
    ('Pelastusarmeija', 'Finnish'),
    ('Ej\u00e9rcito de Salvaci\u00f3n', 'Spanish (accented)'),
    ('Ejercito de Salvacion', 'Spanish (unaccented)'),
    ('Ex\u00e9rcito de Salva\u00e7\u00e3o', 'Portuguese (accented)'),
    ('Exercito de Salvacao', 'Portuguese (unaccented)'),
    ('Armia Zbawienia', 'Polish'),
]

all_sa_ids = set()
for pattern, label in patterns:
    cur = db.execute("SELECT id FROM churches WHERE name LIKE ?", (f'%{pattern}%',))
    ids = set(r[0] for r in cur.fetchall())
    all_sa_ids.update(ids)
    print(f'  {label:30s}: {len(ids):>5}')

print(f'\nTotal unique SA entries in churches: {len(all_sa_ids):,}')

# 2. What's in the hierarchy
hier_ids = set(r[0] for r in db.execute("SELECT church_id FROM sa_hierarchy WHERE church_id IS NOT NULL").fetchall())
print(f'Entries in sa_hierarchy: {len(hier_ids):,}')

# 3. Missing entries
missing = all_sa_ids - hier_ids
extra = hier_ids - all_sa_ids
print(f'\nMissing from hierarchy (in churches but not sa_hierarchy): {len(missing):,}')
print(f'Extra in hierarchy (not in churches SA search): {len(extra):,}')

if missing:
    print('\n=== Missing entries (sample 30) ===')
    cur = db.execute(f"""
        SELECT id, name, city, state, country, source
        FROM churches WHERE id IN ({','.join(str(x) for x in list(missing)[:30])})
        ORDER BY name
    """)
    for r in cur:
        print(f'  {r[0]:>8} | {str(r[1] or ""):60s} | {str(r[2] or ""):20s} | {str(r[3] or ""):10s} | {r[4]:3s} | {str(r[5] or "")}')

    print(f'\n... and {len(missing) - 30} more')

if extra:
    print('\n=== Extra entries (in hierarchy but not matching SA patterns) ===')
    cur = db.execute(f"""
        SELECT h.id, h.church_id, h.name, c.name as orig_name
        FROM sa_hierarchy h
        LEFT JOIN churches c ON h.church_id = c.id
        WHERE h.church_id IN ({','.join(str(x) for x in list(extra)[:10])})
        LIMIT 10
    """)
    for r in cur:
        print(f'  h{i}d={r[0]} | church={r[1]} | name={str(r[2])[:60]} | orig={str(r[3])[:60]}')

# 4. Check by source
print('\n=== Missing entries by source ===')
if missing:
    cur = db.execute(f"""
        SELECT source, COUNT(*) FROM churches 
        WHERE id IN ({','.join(str(x) for x in list(missing))})
        GROUP BY source ORDER BY COUNT(*) DESC
    """)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

# 5. Check denomination_affiliation for SA entries not in hierarchy
if missing:
    print('\n=== denomination_affiliation for missing entries ===')
    cur = db.execute(f"""
        SELECT COALESCE(denomination_affiliation, '(NULL)'), COUNT(*) FROM churches 
        WHERE id IN ({','.join(str(x) for x in list(missing))})
        GROUP BY denomination_affiliation ORDER BY COUNT(*) DESC
    """)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

# 6. Check foreign language entries specifically
print('\n=== Foreign language entries not in hierarchy ===')
for pattern, label in [
    ('Ejercito de Salvacion', 'Spanish unaccented'),
    ('Exercito de Salvacao', 'Portuguese unaccented'),
]:
    cur = db.execute("""
        SELECT c.id, c.name, c.city, c.country 
        FROM churches c LEFT JOIN sa_hierarchy h ON c.id = h.church_id
        WHERE c.name LIKE ? AND h.church_id IS NULL
        LIMIT 10
    """, (f'%{pattern}%',))
    results = cur.fetchall()
    if results:
        print(f'\n{label}:')
        for r in results:
            print(f'  {r[0]:>8} | {str(r[1])[:60]:60s} | {str(r[2] or ""):20s} | {r[3]}')
    else:
        print(f'\n{label}: All covered')

db.close()

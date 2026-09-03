"""Check and fix suffragan diocese -> archdiocese links."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=60)

# Check metro_key format in territories
print('=== Metro key samples ===')
for r in db.execute("SELECT name, full_name, metro_key, dio_type, dio_type_label FROM ecclesiastical_territories WHERE metro_key IS NOT NULL LIMIT 20"):
    print(f'  {str(r[0]):30s} | {str(r[1]):45s} | metro={str(r[2] or "-"):10s} | type={r[3]} ({r[4]})')

# Build name <-> code maps
territory_by_code = {}  # code -> name
territory_by_name = {}  # name -> code
for r in db.execute("SELECT name, full_name, metro_key, dio_type FROM ecclesiastical_territories"):
    name = r[0].lower().strip()
    full = r[1].lower().strip()
    code = r[2].lower().strip() if r[2] else None
    
    if code:
        territory_by_code[code] = name
    
    # Map full name patterns
    territory_by_name[name] = code

print(f'\n  Codes mapped: {len(territory_by_code)}')
print(f'  Names mapped: {len(territory_by_name)}')

# Check how many territories have metro_key 
with_metro = db.execute("SELECT COUNT(*) FROM ecclesiastical_territories WHERE metro_key IS NOT NULL").fetchone()[0]
print(f'  Territories with metro_key: {with_metro:,}')

# Check how many metro_keys resolve to a territory name
resolved = 0
unresolved = []
for code, name in territory_by_code.items():
    if name in territory_by_name:
        resolved += 1
    else:
        unresolved.append(code)

print(f'  Resolved: {resolved}')
print(f'  Unresolved codes (sample): {unresolved[:20]}')

# Fix approach: load all territories, build code->id map FIRST
print('\n=== Building code-to-ID map ===')
code_to_id = {}
name_to_id = {}
for r in db.execute("SELECT id, name, full_name FROM ecclesiastical_territories"):
    name_to_id[r[1].lower()] = r[0]
    name_to_id[r[2].lower()] = r[0]

# Check territory id -> hierarchy id mapping
print('\n=== Checking hierarchy id mapping ===')
for r in db.execute("SELECT id, territory_id, name, cath_type FROM catholic_hierarchy WHERE territory_id IS NOT NULL LIMIT 15"):
    print(f'  h_id={r[0]:>5} | t_id={r[1]:>5} | {str(r[2])[:50]:50s} | {r[3]}')

# Count current links vs potential
current_links = db.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE relationship='suffragan_of'").fetchone()[0]
print(f'\nCurrent suffragan links: {current_links}')

# All suffragan-eligible territories (type d/e/p/t/m/l with metro_key)
eligible = db.execute("""
    SELECT COUNT(*) FROM ecclesiastical_territories 
    WHERE dio_type IN ('d', 'e', 'p', 't', 'm', 'l') AND metro_key IS NOT NULL
""").fetchone()[0]
print(f'Eligible suffragan dioceses: {eligible}')

# Archdioceses (type a/ar)
arch_count = db.execute("""
    SELECT COUNT(*) FROM ecclesiastical_territories 
    WHERE dio_type IN ('a', 'ar')
""").fetchone()[0]
print(f'Archdioceses: {arch_count}')

db.close()

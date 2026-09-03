"""
Deduplicate diocese corporations and map each to its cathedral.

Strategy:
1. Restore unique corps from merge_temp backup (1 copy per unique name)
2. Deduplicate existing corps in main DB to 1 copy per name
3. Parse diocese names from corporation names
4. Match each diocese corp to its cathedral via name + location
5. Copy cathedral coordinates to the corp record; tag as diocese_administration
"""
import sqlite3
import re
import sys

DB = r'E:\grid\churches.db'
BACKUP = r'E:\grid\churches_merge_temp.db'

STATE_MAP = {'ON': 'CA', 'QC': 'CA', 'BC': 'CA', 'AB': 'CA', 'SK': 'CA', 'MB': 'CA',
             'NS': 'CA', 'NB': 'CA', 'NL': 'CA', 'PE': 'CA', 'YT': 'CA', 'NT': 'CA', 'NU': 'CA'}

main_db = sqlite3.connect(DB)
CUR_COLS = [r[1] for r in main_db.execute("PRAGMA table_info(churches)").fetchall()]

# █████████████████████████████████████████████████████████████████████████████
# PART 1: Identify all unique diocese corporation names
# █████████████████████████████████████████████████████████████████████████████

# These patterns define what we consider a "diocese corporation"
DIOCESE_CORP_PATTERNS = [
    '%ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%THE ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%CATHOLIC EPISCOPAL CORPORATION%',
    '%EPISCOPAL CORPORATION OF%',
    '%EPISCOPAL CORPORATION FOR%',
    '%LA CORPORATION EPISCOPALE%',
    '%LA CORPORATION DE LA%',
    '%LA CORPORATION DE L%',
]

def is_diocese_corp(name):
    """Check if a name matches any diocese corporation pattern."""
    if not name:
        return False
    upper = name.upper()
    for pat_text in [
        'ROMAN CATHOLIC EPISCOPAL CORPORATION',
        'CATHOLIC EPISCOPAL CORPORATION',
        'EPISCOPAL CORPORATION OF',
        'EPISCOPAL CORPORATION FOR',
        'LA CORPORATION EPISCOPALE',
    ]:
        if pat_text in upper:
            return True
    return False

# All unique corp names from backup
bdb = sqlite3.connect(BACKUP)
b_cols = [r[1] for r in bdb.execute("PRAGMA table_info(churches)").fetchall()]

unique_backup = {}
cur = bdb.execute("SELECT * FROM churches WHERE name LIKE '%CORPORATION%' ORDER BY id")
for row in cur.fetchall():
    rdata = dict(zip(b_cols, row))
    name = rdata.get('name', '')
    if name not in unique_backup:
        unique_backup[name] = rdata
    # Keep the row with the most non-null data
    else:
        existing_count = sum(1 for v in unique_backup[name].values() if v)
        new_count = sum(1 for v in rdata.values() if v)
        if new_count > existing_count:
            unique_backup[name] = rdata

print(f"=== Unique corporation names in backup: {len(unique_backup)} ===")

# Separate into diocese corps vs other corps
diocese_backup = {n: d for n, d in unique_backup.items() if is_diocese_corp(n)}
other_backup = {n: d for n, d in unique_backup.items() if not is_diocese_corp(n)}
print(f"  Diocese corps: {len(diocese_backup)}")
print(f"  Other corps: {len(other_backup)}")

# █████████████████████████████████████████████████████████████████████████████
# PART 2: Parse diocese name from corporation name for matching
# █████████████████████████████████████████████████████████████████████████████

def extract_diocese_name(corp_name):
    """Extract diocese/city name from a corporation name."""
    name = corp_name.upper().strip()

    # Remove leading La/The
    name = re.sub(r'^(?:LA\s+|THE\s+)', '', name)

    # Remove bilingual suffixes: / La Corporation...
    name = re.sub(r'\s*/\s*LA\s+CORPORATION.*', '', name)
    name = re.sub(r'\s*/\s*ROMAN\s+CATHOLIC.*', '', name)

    # Extract from patterns:
    # "ROMAN CATHOLIC EPISCOPAL CORPORATION FOR THE DIOCESE OF X" -> X
    m = re.search(r'(?:FOR\s+THE\s+)?(?:DIOCESE|ARCHDIOCESE)\s+OF\s+(.+?)(?:\s*,?\s*IN\s+(?:CANADA|ONTARIO|ON))?\s*$', name)
    if m:
        return m.group(1).strip().rstrip(',')

    # "ROMAN CATHOLIC EPISCOPAL CORPORATION OF THE DIOCESE OF X" -> X
    m = re.search(r'OF\s+THE\s+(?:DIOCESE|ARCHDIOCESE)\s+OF\s+(.+?)(?:\s*,?\s*IN\s+(?:CANADA|ONTARIO|ON))?\s*$', name)
    if m:
        return m.group(1).strip().rstrip(',')

    # "ROMAN CATHOLIC EPISCOPAL CORPORATION OF X" -> X
    m = re.search(r'CORPORATION\s+OF\s+(.+?)$', name)
    if m:
        diocese = m.group(1).strip().rstrip(',')
        # Skip if it still contains 'CORPORATION' or 'EPISCOPAL'
        if not re.search(r'CORPORATION|EPISCOPAL|CATHOLIC\s+ROMAN|BISHOP|PRESIDING', diocese):
            return diocese

    # "LA CORPORATION EPISCOPALE CATHOLIQUE ROMAINE DE X" -> X
    m = re.search(r'DE\s+(?:LA\s+)?(.+?)$', name)
    if m:
        diocese = m.group(1).strip().rstrip(',')
        if len(diocese) > 3 and diocese not in ('COMMUNAUTE', 'COMMUNITY'):
            return diocese

    # "CATHOLIC EPISCOPAL CORPORATION OF X" -> X
    m = re.search(r'CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+OF\s+(.+?)$', name)
    if m:
        return m.group(1).strip().rstrip(',')

    # "EPISCOPAL CORPORATION OF X" -> X
    m = re.search(r'EPISCOPAL\s+CORPORATION\s+(?:OF|FOR)\s+(.+?)$', name)
    if m:
        return m.group(1).strip().rstrip(',')

    return None


# Test extraction on some names
print("\n=== Diocese name extraction (sample) ===")
for name in list(diocese_backup.keys())[:20]:
    d = extract_diocese_name(name)
    print(f"  {d or '?'} | {name[:70]}")

# █████████████████████████████████████████████████████████████████████████████
# PART 3: Find cathedrals for each diocese
# █████████████████████████████████████████████████████████████████████████████

def find_cathedral(diocese_name, main_db):
    """Find the cathedral for a given diocese name."""
    if not diocese_name:
        return None

    dname = diocese_name.upper().strip()

    # Try exact match: cathedral name contains diocese name
    cur = main_db.execute("""
        SELECT id, name, city, state, country, latitude, longitude 
        FROM churches 
        WHERE (name LIKE '%CATHEDRAL%' OR name LIKE '%BASILICA%')
          AND latitude IS NOT NULL AND latitude != 0
          AND name LIKE ?
        LIMIT 5
    """, (f'%{dname}%',))
    results = cur.fetchall()
    if results:
        return results[0]

    # Try city match: cathedral in city matching diocese name
    cur = main_db.execute("""
        SELECT id, name, city, state, country, latitude, longitude 
        FROM churches 
        WHERE (name LIKE '%CATHEDRAL%' OR name LIKE '%BASILICA%')
          AND latitude IS NOT NULL AND latitude != 0
          AND (city LIKE ? OR state LIKE ? OR name LIKE ?)
        LIMIT 5
    """, (f'%{dname}%', f'%{dname}%', f'%{dname}%'))
    results = cur.fetchall()

    # If too many results, prefer Catholic cathedrals
    if len(results) > 10:
        cur = main_db.execute("""
            SELECT id, name, city, state, country, latitude, longitude 
            FROM churches 
            WHERE (name LIKE '%CATHEDRAL%' OR name LIKE '%BASILICA%')
              AND latitude IS NOT NULL AND latitude != 0
              AND denomination LIKE '%Catholic%'
              AND (city LIKE ? OR name LIKE ?)
            LIMIT 3
        """, (f'%{dname}%', f'%{dname}%'))
        results = cur.fetchall()

    return results[0] if results else None


# Match diocese corps to cathedrals
print(f"\n=== Cathedral matching ===")
matched = 0
unmatched = 0
matches = []
for name, rdata in sorted(diocese_backup.items()):
    dname = extract_diocese_name(name)
    if dname:
        cathedral = find_cathedral(dname, main_db)
        if cathedral:
            matched += 1
            matches.append((name, rdata, dname, cathedral))
            print(f"  ✓ {dname[:25]:25s} → {cathedral[1][:50]}")
        else:
            unmatched += 1
            print(f"  ✗ {dname[:25]:25s} | {name[:60]}")
    else:
        unmatched += 1
        print(f"  ? {'?':25s} | {name[:60]}")

print(f"\nMatched: {matched}, Unmatched: {unmatched}")

# Show unmatched details for manual review
if unmatched > 0:
    print(f"\n=== Unmatched details ===")
    for name, rdata in sorted(diocese_backup.items()):
        dname = extract_diocese_name(name)
        if not dname or not find_cathedral(dname, main_db):
            city = rdata.get('city', '') or ''
            state = rdata.get('state', '') or ''
            print(f"  {dname or '?':25s} | city={city}, state={state} | {name[:60]}")

bdb.close()
main_db.close()

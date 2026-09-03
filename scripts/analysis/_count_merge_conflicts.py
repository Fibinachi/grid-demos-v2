"""
Count overture merge conflicts — state in name vs state in columns
"""
import sqlite3, re

db = sqlite3.connect(r'E:\grid\churches.db')
db.row_factory = sqlite3.Row

street_pattern = re.compile(
    r'\b(\d{1,5})\s+((?:N(?:ORTH)?\.?\s*|S(?:OUTH)?\.?\s*|E(?:AST)?\.?\s*|W(?:EST)?\.?\s*)?'
    r'[A-Z][A-Za-z.\s]+?)\s+(STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|BOULEVARD|BLVD|'
    r'PKWY|PARKWAY|LANE|LN|CIRCLE|CIR|COURT|CT|PLACE|PL|WAY|HWY|HIGHWAY)',
    re.IGNORECASE)

rows = db.execute("SELECT rowid, name, address, city, state, source FROM churches WHERE LENGTH(name) > 50 AND source LIKE '%overture%'").fetchall()

conflicts = 0
no_conflict = 0
total = 0
for r in rows:
    m = street_pattern.search(r['name'])
    if m:
        total += 1
        name_state = re.search(r'\b([A-Z]{2})\s*(?:\d{5})?\s*$', r['name'])
        col_state = (r['state'] or '').strip()
        if name_state and col_state and name_state.group(1) != col_state:
            conflicts += 1
            if conflicts <= 5:
                print(f"rowid={r['rowid']}")
                print(f"  name:  {r['name'][:120]}")
                print(f"  col state: {col_state} | name state: {name_state.group(1)}")
                print()
        else:
            no_conflict += 1

print(f"Total overture street-in-name: {total}")
print(f"State CONFLICTS (column wrong): {conflicts}")
print(f"No state conflict: {no_conflict}")

"""
Look at merge error examples — names that have BOTH street address and ZIP.
"""
import sqlite3, re

db = sqlite3.connect(r'E:\grid\churches.db')
db.row_factory = sqlite3.Row

zip_at_end = re.compile(r'\b\d{5}(-\d{4})?\s*$')
street_addr = re.compile(
    r'\b\d{1,5}\s+(?:N(?:ORTH)?\.?\s*|S(?:OUTH)?\.?\s*|E(?:AST)?\.?\s*|W(?:EST)?\.?\s*)?'
    r'[A-Z][A-Za-z]+(?:\s+(?:STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|BOULEVARD|BLVD|'
    r'PKWY|PARKWAY|LANE|LN|CIRCLE|CIR|COURT|CT|PLACE|PL|WAY|HWY|HIGHWAY))',
    re.IGNORECASE)

rows = db.execute('SELECT rowid, name, address, city, state, zip, zip5, source FROM churches WHERE LENGTH(name) > 50').fetchall()

# Zip + street examples
print("=== BOTH ZIP + STREET (worst merges) ===")
count = 0
for r in rows:
    name = r['name']
    if zip_at_end.search(name) and street_addr.search(name):
        print(f"rowid={r['rowid']} [{r['source']}]")
        print(f"  name:    {name[:150]}")
        print(f"  address: {r['address']}")
        print(f"  city:    {r['city']}")
        print(f"  state:   {r['state']}")
        print(f"  zip:     {r['zip']} / {r['zip5']}")
        print()
        count += 1
        if count >= 15:
            break

# Now show some 'other' category — what about addresses with city+state_nozip?
print("\n=== NAMES WITH CITY, ST (no zip) at end ===")
city_st_re = re.compile(r'\b([A-Z][A-Za-z .-]+?),?\s+([A-Z]{2})\s*$')
count2 = 0
for r in rows:
    name = r['name']
    m = city_st_re.search(name)
    if m and not zip_at_end.search(name) and not street_addr.search(name):
        # Also check that the city name is substantial (not just 'OF' 'AT' etc)
        city = m.group(1).strip()
        if city.upper() in ('OF', 'AT', 'THE', 'AND', 'IN', 'FOR', 'ON', 'TO') or len(city) < 2:
            continue
        if len(city) > 3 or any(c in city for c in ' .'):
            print(f"rowid={r['rowid']} [{r['source']}]")
            print(f"  name:    {name[:150]}")
            print(f"  address: {r['address']}")
            print(f"  city:    {r['city']}")
            print(f"  state:   {r['state']}")
            print(f"  zip:     {r['zip']} / {r['zip5']}")
            print()
            count2 += 1
            if count2 >= 10:
                break

# Street address examples
print("\n=== STREET ADDRESS IN NAME ===")
count3 = 0
for r in rows:
    name = r['name']
    m = street_addr.search(name)
    if m and not zip_at_end.search(name):
        print(f"rowid={r['rowid']} [{r['source']}]")
        print(f"  name:    {name[:150]}")
        print(f"  address: {r['address']}")
        print(f"  city:    {r['city']}")
        print(f"  state:   {r['state']}")
        print(f"  zip:     {r['zip']} / {r['zip5']}")
        print()
        count3 += 1
        if count3 >= 10:
            break

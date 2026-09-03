"""Find actual address-in-name records."""
import sqlite3, re
db = sqlite3.connect(r'E:\grid\churches.db')

# Real address patterns
street_addr = re.compile(r'\b\d{1,5}\s+(?:N(?:ORTH)?\.?\s*|S(?:OUTH)?\.?\s*|E(?:AST)?\.?\s*|W(?:EST)?\.?\s*)?[A-Z][A-Za-z]+(?:\s+(?:STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|BOULEVARD|BLVD|PKWY|PARKWAY|LANE|LN|CIRCLE|CIR|COURT|CT|PLACE|PL|WAY|HWY|HIGHWAY))', re.IGNORECASE)

# ZIP code at end
zip_at_end = re.compile(r'\b\d{5}(-\d{4})?$')

# City, ST ZIP pattern
city_st_zip = re.compile(r',\s*[A-Z]{2}\s+\d{5}')

# Full address with city/state
full_addr = re.compile(r'\d{5}(-\d{4})?\s*$')

rows = db.execute("SELECT rowid, name FROM churches WHERE LENGTH(name) > 50").fetchall()
print(f"Scanning {len(rows)} long names...")

addr_records = []
for rowid, name in rows:
    if zip_at_end.search(name):
        addr_records.append((rowid, name, 'zip_at_end'))
    elif street_addr.search(name):
        addr_records.append((rowid, name, 'street_addr'))

print(f"\nRecords with address in name: {len(addr_records)}")

# Group by type
types = {}
for r, n, t in addr_records:
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items()):
    print(f"  {t}: {c}")

# Show all
print(f"\n{'='*80}")
for rowid, name, typ in addr_records[:50]:
    print(f"  [{typ}] rowid={rowid}: {name[:150]}")

db.close()

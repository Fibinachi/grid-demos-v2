"""Show full details of address-in-name records for pattern analysis."""
import sqlite3, re
db = sqlite3.connect(r'E:\grid\churches.db')

# Show some examples with all address columns
patterns_to_show = [
    # ZIP at end
    r'\b\d{5}(-\d{4})?\s*$',
    # City, ST ZIP
    r',\s*[A-Z]{2}\s+\d{5}',
    # Street number + direction + name
    r'\b\d{1,5}\s+(?:N|S|E|W|NORTH|SOUTH|EAST|WEST)\.?\s+[A-Z]',
    # PO Box
    r'\bP\.?O\.?\s+BOX\s+\d+',
    # COVID articles
    r'COVID',
]

# Get the actual church columns for some
cur = db.execute("""
    SELECT rowid, name, address, city, state, zip, zip5, country 
    FROM churches 
    WHERE rowid IN (7039, 10730, 214216, 405498, 209979, 270181, 131670, 128706, 130994)
""")
for r in cur.fetchall():
    print(f"rowid={r[0]}")
    print(f"  name={r[1][:120]}")
    print(f"  address={r[2]}")
    print(f"  city={r[3]}")
    print(f"  state={r[4]}")
    print(f"  zip={r[5]} / zip5={r[6]}")
    print(f"  country={r[7]}")
    print()

db.close()

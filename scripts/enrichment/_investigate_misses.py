"""Investigate why 260 Boston churches aren't matching property records."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# 1. Check city name variations in MA
cities = conn.execute("""
    SELECT UPPER(city) as city, state, COUNT(*) as cnt 
    FROM churches 
    WHERE state = 'MA' AND city != '' 
    GROUP BY UPPER(city), state 
    ORDER BY cnt DESC
    LIMIT 30
""").fetchall()
print("MA city distribution:")
for c in cities:
    print(f"  {c[0]}: {c[2]}")

# 2. Check if our unmatched churches have addresses we can try
print("\n--- Checking a few unmatched addresses vs property records ---")
unmatched = conn.execute("""
    SELECT ch.id, ch.name, ch.address, cc.value as contact_addr
    FROM churches ch
    LEFT JOIN church_contact_values cc 
        ON cc.church_id = ch.id 
        AND cc.contact_type IN ('address', 'street_address')
    WHERE UPPER(ch.city) = 'BOSTON' AND ch.state = 'MA'
      AND ch.id NOT IN (SELECT id FROM churches WHERE boston_pid IS NOT NULL)
    LIMIT 20
""").fetchall()

print(f"Sample unmatched churches:")
for c in unmatched:
    addr = c[2] or c[3] or '(no addr)'
    print(f"  #{c[0]}: {c[1][:55]} | addr={addr}")

# 3. Check property records for addresses that could match
print("\n--- Loading property records ---")
with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

# Check what ADAMS ST properties look like
for p in props:
    if p.get('ST_NAME') and 'ADAMS' in p.get('ST_NAME').upper():
        print(f"  PROP: {p.get('ST_NUM')} {p.get('ST_NAME')} | {p.get('OWNER')[:50]}")

print("\n--- Street name check: our addresses vs property streets ---")
# Get church addresses
church_addrs = conn.execute("""
    SELECT DISTINCT ch.address
    FROM churches ch
    WHERE UPPER(ch.city) = 'BOSTON' AND ch.state = 'MA'
      AND ch.address IS NOT NULL AND ch.address != ''
      AND ch.id NOT IN (SELECT id FROM churches WHERE boston_pid IS NOT NULL)
    ORDER BY ch.address
""").fetchall()

# Get property streets
prop_streets = set()
for p in props:
    s = p.get('ST_NAME')
    if s:
        prop_streets.add(s.strip().upper())

mismatches = []
for addr_row in church_addrs:
    addr = addr_row[0].strip().upper()
    # Extract just the street name
    import re
    m = re.match(r'^\d+[A-Z]?\s+(.+)$', addr)
    if m:
        street = m.group(1).strip()
        # Normalize suffixes
        street = re.sub(r'\bSTREET\b', 'ST', street)
        street = re.sub(r'\bAVENUE\b', 'AV', street)
        street = re.sub(r'\bROAD\b', 'RD', street)
        street = re.sub(r'\bDRIVE\b', 'DR', street)
        street = re.sub(r'\bLANE\b', 'LN', street)
        street = re.sub(r'\bBOULEVARD\b', 'BLVD', street)
        street = re.sub(r'\bPARKWAY\b', 'PKWY', street)
        street = re.sub(r'\bCOURT\b', 'CT', street)
        street = re.sub(r'\bPLACE\b', 'PL', street)
        street = re.sub(r'\bSQUARE\b', 'SQ', street)
        street = re.sub(r'\bTERRACE\b', 'TER', street)
        street = re.sub(r'\bHIGHWAY\b', 'HWY', street)
        street = re.sub(r'\bCIRCLE\b', 'CIR', street)
        street = re.sub(r'[^\w\s]', '', street).strip()
        
        if street not in prop_streets:
            mismatches.append((addr, street))

print(f"\nStreet names in church addresses NOT in property records ({len(mismatches)}):")
for addr, street in mismatches[:30]:
    print(f"  {addr}  ->  [{street}]")

# 4. Check neighborhood cities
print("\n--- Boston neighborhoods (also might say BOSTON in city field) ---")
hoods = conn.execute("""
    SELECT DISTINCT UPPER(city), state 
    FROM churches 
    WHERE state = 'MA' AND UPPER(city) LIKE '%BOSTON%'
       OR state = 'MA' AND UPPER(city) IN ('DORCHESTER', 'ROXBURY', 'JAMAICA PLAIN', 'HYDE PARK', 
           'EAST BOSTON', 'SOUTH BOSTON', 'CHARLESTOWN', 'BRIGHTON', 'ALLSTON', 
           'WEST ROXBURY', 'ROSALINDALE', 'MATTAPAN')
    ORDER BY UPPER(city)
""").fetchall()
for h in hoods:
    cnt = conn.execute("SELECT COUNT(*) FROM churches WHERE UPPER(city)=? AND state=?", (h[0], h[1])).fetchone()[0]
    print(f"  {h[0]}, {h[1]}: {cnt}")

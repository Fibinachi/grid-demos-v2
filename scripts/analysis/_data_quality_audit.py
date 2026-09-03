"""Comprehensive data quality audit — find normalization opportunities"""
import sqlite3
from collections import Counter
conn = sqlite3.connect('churches.db')
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'Total churches: {total:,}\n')

# ── 1. ADDRESS FORMAT ISSUES ──
print('=== 1. ADDRESSES ===')
has_addr = conn.execute("SELECT COUNT(*) FROM churches WHERE address IS NOT NULL AND address != ''").fetchone()[0]
print(f'  Has address: {has_addr:,} ({100*has_addr/total:.1f}%)')

# ALL CAPS addresses
caps_addr = conn.execute("SELECT COUNT(*) FROM churches WHERE address = UPPER(address) AND address != LOWER(address) AND address != ''").fetchone()[0]
print(f'  ALL CAPS: {caps_addr:,}')

# Addresses with double spaces
dbl_addr = conn.execute("SELECT COUNT(*) FROM churches WHERE address LIKE '%  %'").fetchone()[0]
print(f'  Double spaces: {dbl_addr:,}')

# Address samples
print('  Samples:')
for r in conn.execute("SELECT address, city, state FROM churches WHERE address != '' LIMIT 5").fetchall():
    print(f'    "{r[0][:60]}" | {r[1]} {r[2]}')

# ── 2. CITY ISSUES ──
print('\n=== 2. CITIES ===')
has_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city IS NOT NULL AND city != ''").fetchone()[0]
print(f'  Has city: {has_city:,} ({100*has_city/total:.1f}%)')

# ALL CAPS cities
caps_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city = UPPER(city) AND city != LOWER(city) AND city != ''").fetchone()[0]
print(f'  ALL CAPS: {caps_city:,}')

# City contains state abbreviation (e.g., "Dallas, TX")
city_with_comma = conn.execute("SELECT COUNT(*) FROM churches WHERE city LIKE '%,%'").fetchone()[0]
print(f'  Contains comma (city, state?): {city_with_comma:,}')
for r in conn.execute("SELECT city, state FROM churches WHERE city LIKE '%,%' LIMIT 5").fetchall():
    print(f'    "{r[0]}" | state={r[1]}')

# Saint/St. variations
st_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city LIKE 'ST %' OR city LIKE 'ST.%'").fetchone()[0]
saint_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city LIKE 'SAINT %'").fetchone()[0]
print(f'  "St." cities: {st_city:,} | "Saint" cities: {saint_city:,}')

# Mt./Mount variations
mt_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city LIKE 'MT %' OR city LIKE 'MT.%'").fetchone()[0]
mount_city = conn.execute("SELECT COUNT(*) FROM churches WHERE city LIKE 'MOUNT %'").fetchone()[0]
print(f'  "Mt." cities: {mt_city:,} | "Mount" cities: {mount_city:,}')

# ── 3. STATE ISSUES ──
print('\n=== 3. STATES ===')
has_state = conn.execute("SELECT COUNT(*) FROM churches WHERE state IS NOT NULL AND state != ''").fetchone()[0]
print(f'  Has state: {has_state:,}')

# Non-2-char states
long_state = conn.execute("SELECT COUNT(*) FROM churches WHERE LENGTH(state) > 2 AND state != ''").fetchone()[0]
print(f'  Length > 2 chars: {long_state:,}')
for r in conn.execute("SELECT DISTINCT state, COUNT(*) n FROM churches WHERE LENGTH(state) > 2 GROUP BY 1 ORDER BY 2 DESC LIMIT 12").fetchall():
    print(f'    {r[0]:20s} {r[1]:>8,}')

# Canadian provinces
ca_states = conn.execute("SELECT DISTINCT state, COUNT(*) n FROM churches WHERE state IN ('ON','QC','BC','AB','MB','SK','NS','NB','NL','PE','YT','NT','NU') GROUP BY 1 ORDER BY 2 DESC").fetchall()
if ca_states:
    print(f'  Canadian provinces: {len(ca_states)}')
    for r in ca_states:
        print(f'    {r[0]:5s} {r[1]:>8,}')

# ── 4. ZIP CODE ISSUES ──
print('\n=== 4. ZIP CODES ===')
has_zip = conn.execute("SELECT COUNT(*) FROM churches WHERE zip IS NOT NULL AND zip != ''").fetchone()[0]
print(f'  Has zip: {has_zip:,}')

# 9-digit ZIPs
zip9 = conn.execute("SELECT COUNT(*) FROM churches WHERE zip LIKE '%-%'").fetchone()[0]
print(f'  ZIP+4 format: {zip9:,}')

# ZIP embedded in address
zip_in_addr = conn.execute("SELECT COUNT(*) FROM churches WHERE address LIKE '%_____' AND address GLOB '*[0-9][0-9][0-9][0-9][0-9]'").fetchone()[0]
print(f'  ZIP in address field: ~{zip_in_addr}')

# Invalid ZIP lengths
bad_zip = conn.execute("SELECT COUNT(*) FROM churches WHERE zip != '' AND LENGTH(zip) NOT IN (5,10) AND zip NOT LIKE '%-%'").fetchone()[0]
print(f'  Non-standard ZIP length (not 5 or 10): {bad_zip:,}')

# ── 5. WEBSITE ISSUES ──
print('\n=== 5. WEBSITES ===')
has_web = conn.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
print(f'  Has website: {has_web:,} ({100*has_web/total:.1f}%)')

# http vs https
http = conn.execute("SELECT COUNT(*) FROM churches WHERE website LIKE 'http://%'").fetchone()[0]
https = conn.execute("SELECT COUNT(*) FROM churches WHERE website LIKE 'https://%'").fetchone()[0]
print(f'  http:// : {http:,} | https:// : {https:,}')

# No protocol
no_proto = conn.execute("SELECT COUNT(*) FROM churches WHERE website != '' AND website NOT LIKE 'http%'").fetchone()[0]
print(f'  No protocol: {no_proto:,}')
for r in conn.execute("SELECT website FROM churches WHERE website != '' AND website NOT LIKE 'http%' LIMIT 5").fetchall():
    print(f'    "{r[0][:60]}"')

# Trailing slash
trail_slash = conn.execute("SELECT COUNT(*) FROM churches WHERE website LIKE '%/' AND website LIKE 'http%'").fetchone()[0]
print(f'  Trailing slash: {trail_slash:,}')

# www prefix
www = conn.execute("SELECT COUNT(*) FROM churches WHERE website LIKE '%www.%'").fetchone()[0]
print(f'  Contains www.: {www:,}')

# ── 6. PHONE ISSUES ──
print('\n=== 6. PHONES ===')
has_phone = conn.execute("SELECT COUNT(*) FROM churches WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
print(f'  Has phone: {has_phone:,} ({100*has_phone/total:.1f}%)')

# Various formats
dash = conn.execute("SELECT COUNT(*) FROM churches WHERE phone LIKE '%-%'").fetchone()[0]
dot = conn.execute("SELECT COUNT(*) FROM churches WHERE phone LIKE '%.%'").fetchone()[0]
paren = conn.execute("SELECT COUNT(*) FROM churches WHERE phone LIKE '%(%'").fetchone()[0]
print(f'  Dash format: {dash:,} | Dot format: {dot:,} | Parens: {paren:,}')

for r in conn.execute("SELECT DISTINCT phone FROM churches WHERE phone != '' LIMIT 8").fetchall():
    print(f'    "{r[0]}"')

# ── 7. DENOMINATION NORMALIZATION ──
print('\n=== 7. DENOMINATIONS ===')
# Similar denomination names
similar_denoms = [
    ("'BAPTIST' vs 'BAPTIST CHURCH'", 
     conn.execute("SELECT COUNT(*) FROM churches WHERE denomination='Baptist'").fetchone()[0],
     conn.execute("SELECT COUNT(*) FROM churches WHERE denomination='Baptist Church'").fetchone()[0]),
]
for label, a, b in similar_denoms:
    print(f'  {label}: {a:,} vs {b:,}')

# Top denoms with slight variations
print('  Top denomination variations:')
variations = conn.execute("""
    SELECT denomination, COUNT(*) n FROM churches 
    WHERE denomination IS NOT NULL AND denomination != '' AND denomination != 'Unknown'
    GROUP BY 1 HAVING COUNT(*) > 1000
    ORDER BY 1
""").fetchall()
for r in variations[:15]:
    print(f'    {r[0][:45]:45s} {r[1]:>8,}')

# ── 8. NULL vs EMPTY STRING ──
print('\n=== 8. NULL vs EMPTY STRING ===')
for col in ['address','city','state','zip','phone','website','email','denomination','county_name','county_fips']:
    try:
        nulls = conn.execute(f'SELECT COUNT(*) FROM churches WHERE {col} IS NULL').fetchone()[0]
        empty = conn.execute(f"SELECT COUNT(*) FROM churches WHERE {col} = ''").fetchone()[0]
        if empty > 0:
            print(f'  {col:18s}: NULL={nulls:,}  empty={empty:,}')
    except:
        pass

# ── 9. NEAR-DUPLICATE DETECTION ──
print('\n=== 9. NEAR-DUPLICATE POTENTIAL ===')
# Same name+city+state but different source
near_dups = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT UPPER(name), UPPER(city), UPPER(state), COUNT(*) n
        FROM churches 
        WHERE name != '' AND city != '' AND state != ''
        GROUP BY 1, 2, 3
        HAVING COUNT(*) > 1 AND COUNT(DISTINCT source) > 1
    )
""").fetchone()[0]
print(f'  Name+city+state dupes from DIFFERENT sources: {near_dups:,} (true duplicates)')

# Same name+state, different city (near miss)
near_miss = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT UPPER(name), UPPER(state), COUNT(DISTINCT UPPER(city)) cities
        FROM churches 
        WHERE name != '' AND city != '' AND state != ''
        GROUP BY 1, 2
        HAVING cities > 1 AND COUNT(*) > 2
    )
""").fetchone()[0]
print(f'  Same name+state, multiple cities (generic names): {near_miss:,} groups')

# ── 10. MISSING DATA HEATMAP ──
print('\n=== 10. MISSING DATA HEATMAP ===')
for col, label in [
    ('latitude', 'Coordinates'), ('county_fips', 'County FIPS'), 
    ('tract_fips', 'Tract FIPS'), ('denomination', 'Denomination'),
    ('website', 'Website'), ('phone', 'Phone'), ('email', 'Email'),
    ('county_name', 'County name')
]:
    try:
        has = conn.execute(f"SELECT COUNT(*) FROM churches WHERE {col} IS NOT NULL AND {col} != ''").fetchone()[0]
        print(f'  {label:18s}: {has:>8,} ({100*has/total:5.1f}%)  | missing: {total-has:>8,}')
    except:
        pass

conn.close()

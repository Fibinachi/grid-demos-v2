import sqlite3

db = sqlite3.connect('churches.db')
cur = db.cursor()

# Check: how many of the 411 "JEHOVA" records are not already captured?
already = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%JEHOVAH%' AND name LIKE '%WITNESS%'").fetchone()[0]
total_jehova = cur.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%JEHOVAH%'".replace('AH', 'A')).fetchone()[0]
print(f'Total with JEHOVA pattern: {total_jehova}')
print(f'Of those, confirmed JW (also WITNESS): {already}')
print(f'Remaining potential JW: {total_jehova - already}')

# Show the edge cases - "JEHOVA" without "WITNESS"
rows = cur.execute("""
    SELECT name, city, state FROM churches 
    WHERE name LIKE '%JEHOVAH%' AND name NOT LIKE '%WITNESS%'
    ORDER BY state, city LIMIT 30
""").fetchall()
print('\n=== JEHOVAH without WITNESS (first 30) ===')
# These could be "Jehovah Jireh", "Jehovah Shalom" etc. - not JW
# or they could be variants like "JEHOVAHS" truncated
for r in rows:
    print(f'  {r[0][:65]:65s} {r[1] or "":15s} {r[2] or "":2s}')

# Check if Overture data has JW
overture_jw = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%overture%' AND (name LIKE '%Jehovah%' OR name LIKE '%Kingdom Hall%')").fetchone()[0]
print(f'\nOverture JW records: {overture_jw}')

# Check PSS data
pss_jw = cur.execute("SELECT COUNT(*) FROM churches WHERE source='pss' AND (name LIKE '%Jehovah%' OR name LIKE '%Kingdom Hall%')").fetchone()[0]
print(f'PSS JW records: {pss_jw}')

# Check enriched data
enr_jw = cur.execute("SELECT COUNT(*) FROM churches WHERE source LIKE '%enrich%' AND (name LIKE '%Jehovah%' OR name LIKE '%Kingdom Hall%')").fetchone()[0]
print(f'Enriched JW records: {enr_jw}')

db.close()

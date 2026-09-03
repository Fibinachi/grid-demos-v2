import sqlite3
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
print(f'Total: {total:,}')

# 1. Drop leading THE
n = conn.execute("UPDATE churches SET name = LTRIM(SUBSTR(name, 4)) WHERE UPPER(name) LIKE 'THE %'").rowcount
print(f'1. Leading THE dropped: {n:,}')

# 2. Drop trailing THE  
n2 = conn.execute("UPDATE churches SET name = RTRIM(SUBSTR(name, 1, LENGTH(name)-4)) WHERE UPPER(name) LIKE '% THE' AND UPPER(name) NOT LIKE '% OF THE' AND UPPER(name) NOT LIKE '% IN THE' AND UPPER(name) NOT LIKE '% ON THE' AND UPPER(name) NOT LIKE '% AT THE'").rowcount
print(f'2. Trailing THE dropped: {n2:,}')

# 3. Collapse spaces
n3 = 0
while True:
    c = conn.execute("UPDATE churches SET name = REPLACE(name, '  ', ' ') WHERE name LIKE '%  %'").rowcount
    if c == 0: break
    n3 += c
print(f'3. Spaces collapsed in {n3} names')

# 4. Trailing periods (preserve INC, LLC, etc)
n4 = conn.execute("UPDATE churches SET name = RTRIM(name, '.') WHERE name LIKE '%.' AND UPPER(name) NOT LIKE '%INC.' AND UPPER(name) NOT LIKE '%LLC.' AND UPPER(name) NOT LIKE '%LTD.' AND UPPER(name) NOT LIKE '%CORP.' AND UPPER(name) NOT LIKE '%JR.' AND UPPER(name) NOT LIKE '%SR.' AND UPPER(name) NOT LIKE '%DR.'").rowcount
print(f'4. Trailing periods: {n4:,}')

# 5. Trailing commas
n5 = conn.execute("UPDATE churches SET name = RTRIM(name, ',') WHERE name LIKE '%,'").rowcount
print(f'5. Trailing commas: {n5:,}')

# 6. UPPERCASE
n6 = conn.execute("UPDATE churches SET name = UPPER(name) WHERE name != UPPER(name)").rowcount
print(f'6. Uppercased: {n6:,}')

# 7. Trim
n7 = conn.execute("UPDATE churches SET name = TRIM(name) WHERE name != TRIM(name)").rowcount
print(f'7. Trimmed: {n7:,}')

conn.commit()

# Verify
r = conn.execute("SELECT COUNT(*) FROM churches WHERE UPPER(name) LIKE 'THE %'").fetchone()[0]
nu = conn.execute('SELECT COUNT(*) FROM churches WHERE name != UPPER(name)').fetchone()[0]
print(f'\nLeading THE remaining: {r}')
print(f'Not uppercase: {nu}')

print('\nSamples:')
for row in conn.execute('SELECT name, city, state, source FROM churches ORDER BY RANDOM() LIMIT 8').fetchall():
    print(f'  {row[0][:55]:55s}  {row[1]:15s} {row[2]}  ({row[3]})')

conn.close()
print('Done.')

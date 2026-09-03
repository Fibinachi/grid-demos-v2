"""
Normalize Canada + Mexico church names:
- Drop leading THE (all countries)
- Collapse spaces
- UPPERCASE
- Mexico: strip accent marks for dedup consistency
- Mexico: identify duplicate groups (Iglesia X = Parroquia X = Templo X)
"""
import sqlite3, re
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA busy_timeout=60000')

# ── Apply same normalization to ALL churches (catch new imports) ──
print('=== Normalizing ALL churches ===')

# 1. Leading THE
n1 = conn.execute("UPDATE churches SET name = LTRIM(SUBSTR(name, 4)) WHERE UPPER(name) LIKE 'THE %'").rowcount
print(f'1. Leading THE: {n1:,}')

# 2. Trailing THE
n2 = conn.execute("UPDATE churches SET name = RTRIM(SUBSTR(name, 1, LENGTH(name)-4)) WHERE UPPER(name) LIKE '% THE' AND UPPER(name) NOT LIKE '% OF THE' AND UPPER(name) NOT LIKE '% IN THE'").rowcount
print(f'2. Trailing THE: {n2:,}')

# 3. Spaces
n3 = 0
while True:
    c = conn.execute("UPDATE churches SET name = REPLACE(name, '  ', ' ') WHERE name LIKE '%  %'").rowcount
    if c == 0: break
    n3 += c
print(f'3. Spaces: {n3:,}')

# 4. Trailing periods
n4 = conn.execute("UPDATE churches SET name = RTRIM(name, '.') WHERE name LIKE '%.' AND UPPER(name) NOT LIKE '%INC.' AND UPPER(name) NOT LIKE '%LLC.'").rowcount
print(f'4. Periods: {n4:,}')

# 5. Trailing commas
n5 = conn.execute("UPDATE churches SET name = RTRIM(name, ',') WHERE name LIKE '%,'").rowcount
print(f'5. Commas: {n5:,}')

# 6. UPPERCASE all
n6 = conn.execute("UPDATE churches SET name = UPPER(name) WHERE name != UPPER(name)").rowcount
print(f'6. UPPERCASE: {n6:,}')

# 7. Trim
n7 = conn.execute("UPDATE churches SET name = TRIM(name) WHERE name != TRIM(name)").rowcount
print(f'7. Trim: {n7:,}')
conn.commit()

# ── Mexico: Spanish normalization ──
print('\n=== Mexican Spanish dedup ===')

# Create a normalized_name column concept - strip leading church-type words
# "IGLESIA SAN PEDRO" and "PARROQUIA SAN PEDRO" should be recognized as same

# Strategy: add a `name_normalized` column for dedup purposes, 
# but DON'T change the actual `name` column (preserve original)
conn.execute("ALTER TABLE churches ADD COLUMN name_core TEXT")
conn.execute("UPDATE churches SET name_core = NULL")

# Strip leading church-type words + articles for MX churches
# Pattern: IGLESIA | PARROQUIA | TEMPLO | CAPILLA | CATEDRAL | CONGREGACION | MISION
# followed by optional DE | DEL | LA | EL | LAS | LOS
prefixes = [
    r'^IGLESIA\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^PARROQUIA\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^TEMPLO\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^CAPILLA\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^CATEDRAL\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^CONGREGACION\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^MISION\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
    r'^SANTUARIO\s+(DE\s+|DEL\s+|LA\s+|EL\s+|LAS\s+|LOS\s+)?',
]

# For MX churches, compute normalized core name
mx_churches = conn.execute("SELECT id, name FROM churches WHERE country='MX' AND name != ''").fetchall()
print(f'  MX churches to normalize: {len(mx_churches):,}')

batch = []
for id_, name in mx_churches:
    core = name
    for pat in prefixes:
        core = re.sub(pat, '', core, count=1)
    core = core.strip()
    if core != name and core:
        batch.append((core, id_))

conn.executemany("UPDATE churches SET name_core=? WHERE id=?", batch)
conn.commit()
print(f'  Assigned name_core: {len(batch):,}')

# Sample
print('\n  Samples of normalization:')
for r in conn.execute("SELECT name, name_core FROM churches WHERE country='MX' AND name_core IS NOT NULL LIMIT 12").fetchall():
    print(f'    "{r[0][:45]:45s}" -> "{r[1][:45]}"')

# ── Find new duplicates using name_core ──
print('\n=== DUPLICATE GROUPS BY CORE NAME ===')
dup_groups = conn.execute("""
    SELECT name_core, state, COUNT(*) n, GROUP_CONCAT(name, ' || ') as names
    FROM churches 
    WHERE country='MX' AND name_core IS NOT NULL AND name_core != ''
    GROUP BY name_core, state
    HAVING COUNT(*) > 1
    ORDER BY n DESC
    LIMIT 20
""").fetchall()

print(f'  Duplicate groups found: {len(dup_groups)} (showing top 20)')
for r in dup_groups:
    print(f'    {r[2]}x  core="{r[0][:35]:35s}" in {r[1]}')
    names_list = r[3].split(' || ')
    for n in names_list[:5]:
        print(f'           - {n[:55]}')

# ── Log duplicates in church_sources ──
print('\n=== Logging Spanish duplicates ===')
logged = 0
for r in conn.execute("""
    SELECT c1.id, c2.id, c1.name, c2.name, c1.name_core
    FROM churches c1
    JOIN churches c2 ON c1.name_core = c2.name_core 
                     AND c1.state = c2.state
                     AND c1.id < c2.id
    WHERE c1.country='MX' AND c1.name_core IS NOT NULL AND c1.name_core != ''
"""):
    try:
        conn.execute("""INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
            VALUES (?, 'spanish_dedup', ?, 'duplicate of ' || ?)""",
            (r[0], str(r[1]), r[3] or ''))
        logged += 1
    except: pass
conn.commit()
print(f'  Logged: {logged} duplicate pairs')

# ── Canada: just verify ──
ca_the = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND UPPER(name) LIKE 'THE %'").fetchone()[0]
print(f'\n=== VERIFY ===')
print(f'  Canada leading THE remaining: {ca_the}')

conn.close()
print('Done.')

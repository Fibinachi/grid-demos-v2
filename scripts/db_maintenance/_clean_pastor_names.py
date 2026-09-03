"""Strip pastor names from church names to standardize."""
import sqlite3, re

conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# ── Find candidates ──────────────────────────────────────────────────────────
c.execute("""SELECT COUNT(*) FROM churches 
WHERE LOWER(name) LIKE '% pastor %' OR LOWER(name) LIKE '% - pastor %' 
   OR LOWER(name) LIKE '%–pastor%' OR LOWER(name) LIKE '%(pastor%'
   OR LOWER(name) LIKE '%pastora %' OR LOWER(name) LIKE '%pastori %'
   OR LOWER(name) LIKE '%pastoral %' AND LOWER(name) NOT LIKE '%pastoral charge%'
   AND LOWER(name) NOT LIKE '%pastoral center%' AND LOWER(name) NOT LIKE '%pastoral centre%'""")
total = c.fetchone()[0]
print(f"Candidates with pastor names: {total:,}")

# ── Show samples ─────────────────────────────────────────────────────────────
c.execute("""SELECT id, name FROM churches 
WHERE LOWER(name) LIKE '% pastor %' AND LOWER(name) NOT LIKE '%buen pastor%'
   AND LOWER(name) NOT LIKE '%good pastor%' AND LOWER(name) NOT LIKE '%bom pastor%'
LIMIT 20""")
print("\nEnglish pattern 'CHURCH PASTOR NAME':")
for rid, name in c.fetchall():
    print(f"  {str(name)[:70]}")

c.execute("""SELECT id, name FROM churches 
WHERE (LOWER(name) LIKE '% - pastor %' OR LOWER(name) LIKE '%–pastor %')
LIMIT 20""")
print("\nPattern 'CHURCH - Pastor Name':")
for rid, name in c.fetchall():
    print(f"  {str(name)[:70]}")

# ── Apply fixes ──────────────────────────────────────────────────────────────
cleaned = 0

# Pattern 1: "CHURCH NAME PASTOR SURNAME" → "CHURCH NAME"
# Match: " PASTOR " followed by one or two words at end
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), ' PASTOR ') - 1))
WHERE UPPER(name) LIKE '% PASTOR %'
AND UPPER(name) NOT LIKE '%BUEN PASTOR%' AND UPPER(name) NOT LIKE '%GOOD PASTOR%'
AND UPPER(name) NOT LIKE '%BOM PASTOR%' AND UPPER(name) NOT LIKE '%PASTORAL CHARGE%'
AND UPPER(name) NOT LIKE '%PASTORAL CENTER%' AND UPPER(name) NOT LIKE '%PASTORAL CENTRE%'
AND UPPER(name) NOT LIKE '%PASTORAL CARE%' AND UPPER(name) NOT LIKE '%PASTORAL COUNSEL%'
AND UPPER(name) NOT LIKE '%PASTORAL INSTITUTE%' AND UPPER(name) NOT LIKE '%PASTORAL OFFICE%'
AND LENGTH(name) - LENGTH(REPLACE(UPPER(name), ' PASTOR ', '')) > 8""")
print(f"\n'CHURCH PASTOR NAME' → 'CHURCH': {c.rowcount}")
cleaned += c.rowcount

# Pattern 2: "CHURCH - Pastor Name" or "CHURCH – Pastor Name"
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(name, ' - Pastor') - 1))
WHERE name LIKE '% - Pastor%'""")
print(f"'CHURCH - Pastor...' → 'CHURCH': {c.rowcount}")
cleaned += c.rowcount

c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(name, '–Pastor') - 1))
WHERE name LIKE '%–Pastor%'""")
print(f"'CHURCH–Pastor...' → 'CHURCH': {c.rowcount}")
cleaned += c.rowcount

# Pattern 3: "CHURCH (Pastor Name)" → "CHURCH"
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(name, '(Pastor') - 1))
WHERE name LIKE '%(Pastor%' AND name NOT LIKE '%buen pastor%' AND name NOT LIKE '%bom pastor%'""")
print(f"'CHURCH (Pastor...' → 'CHURCH': {c.rowcount}")
cleaned += c.rowcount

# Pattern 4: Spanish/Portuguese "Iglesia ... Pastor Nombre"
c.execute("""UPDATE churches SET name = TRIM(SUBSTR(name, 1, INSTR(UPPER(name), ' PASTOR ') - 1))
WHERE (LOWER(name) LIKE '%iglesia%' OR LOWER(name) LIKE '%igreja%' OR LOWER(name) LIKE '%assembléia%' OR LOWER(name) LIKE '%assembleia%')
AND UPPER(name) LIKE '% PASTOR %'
AND UPPER(name) NOT LIKE '%BUEN PASTOR%' AND UPPER(name) NOT LIKE '%BOM PASTOR%'""")
print(f"Spanish/Portuguese 'Iglesia ... Pastor...' → church name: {c.rowcount}")
cleaned += c.rowcount

conn.commit()
print(f"\nTotal names cleaned: {cleaned}")

# ── Verify ───────────────────────────────────────────────────────────────────
c.execute("""SELECT name FROM churches 
WHERE LOWER(name) LIKE '% pastor %' AND LOWER(name) NOT LIKE '%buen pastor%'
   AND LOWER(name) NOT LIKE '%good pastor%' AND LOWER(name) NOT LIKE '%bom pastor%'
   AND LOWER(name) NOT LIKE '%pastoral charge%' AND LOWER(name) NOT LIKE '%pastoral center%'
LIMIT 10""")
remaining = c.fetchall()
print(f"\nRemaining ' PASTOR ' patterns: {len(remaining)}")
for (name,) in remaining:
    print(f"  {name[:70]}")

conn.close()

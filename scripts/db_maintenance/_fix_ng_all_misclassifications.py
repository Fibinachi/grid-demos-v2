"""Fix all remaining Nigeria faith misclassifications found in audit."""
import sqlite3
db = sqlite3.connect('e:/grid/churches.db')
db.row_factory = sqlite3.Row

print('Fixing Nigeria misclassifications...')
total_fixed = 0

# 1. Buddhist → Christian (all are Christian churches misplaced)
#    Except the Thai-named one which is GPS-misplaced, and the Zawiyat which is Islam
db.execute("""
    UPDATE churches SET faith='Christian', tradition='Protestant', 
        taxonomy_id=2, landmark_type='church'
    WHERE country='NG' AND faith='Buddhist'
        AND name NOT LIKE '%วัด%' AND name NOT LIKE '%Zawiyat%'
""")
n = db.total_changes
print(f'  Buddhist→Christian: {n}')
total_fixed += n

db.execute("""
    UPDATE churches SET faith='Islam', tradition='Sunni', taxonomy_id=4
    WHERE country='NG' AND faith='Buddhist' AND name LIKE '%Zawiyat%'
""")
n = db.total_changes
print(f'  Buddhist(Zawiyat)→Islam: {n}')
total_fixed += n

# The Thai temple (วัด) - leave as Buddhist for now, likely GPS-misplaced but not wrong faith

# 2. Judaism → Christian (all are Christian churches)
db.execute("""
    UPDATE churches SET faith='Christian', tradition='Protestant',
        taxonomy_id=2, landmark_type='church'
    WHERE country='NG' AND faith='Judaism'
        AND name NOT LIKE '%Gihon Hebrew%'
""")
n = db.total_changes
print(f'  Judaism→Christian: {n}')
total_fixed += n

# Gihon Hebrews Synagogue - could be real Igbo Jewish community. Keep as Judaism but fix landmark_type
db.execute("""
    UPDATE churches SET landmark_type='synagogue'
    WHERE country='NG' AND faith='Judaism' AND name LIKE '%Gihon Hebrew%'
""")
n = db.total_changes
print(f'  Judaism (Gihon Hebrews): {n} (type fix only)')

# 3. Shinto → Other (African traditional shrine)
db.execute("""
    UPDATE churches SET faith='Other', tradition='Traditional African',
        taxonomy_id=674, landmark_type='shrine'
    WHERE country='NG' AND faith='Shinto'
""")
n = db.total_changes
print(f'  Shinto→Other (Traditional African): {n}')
total_fixed += n

# 4. Other → Christian (where taxonomy is clearly Christian)
# These are Wikidata imports where Wikidata labeled Christian churches as "shrine"
christian_tax_ids = [2, 14, 152, 209, 214, 218, 219, 333, 356, 392]
for tid in christian_tax_ids:
    db.execute("""
        UPDATE churches SET faith='Christian', landmark_type='church'
        WHERE country='NG' AND faith='Other' AND taxonomy_id=?
    """, [tid])
    n = db.total_changes
    if n > 0:
        # Get tradition name
        tname = db.execute("SELECT name FROM taxonomy WHERE id=?", [tid]).fetchone()
        tname = tname[0] if tname else str(tid)
        print(f'  Other(tax={tid} {tname})→Christian: {n}')
        total_fixed += n

# 5. Other with tax_id=6 (generic Other) — split:
#    type='shrine' from Wikidata → Christian (same Wikidata batch issue)
#    type='temple' from Wikidata → Christian
#    Keep traditional shrines (from osm_import, holy_sites_import)
db.execute("""
    UPDATE churches SET faith='Christian', tradition='Protestant',
        taxonomy_id=2, landmark_type='church'
    WHERE country='NG' AND faith='Other' AND taxonomy_id=6
        AND source LIKE '%wikidata%'
""")
n = db.total_changes
print(f'  Other(tax=6 wikidata)→Christian: {n}')
total_fixed += n

# Remaining Other entries: mostly Traditional African (tax=674) — these are legitimate

db.commit()

# Also fix Hindu (may not have persisted from prior fix)
print('\nAlso fixing Hindu in Nigeria...')
db.execute("""
    UPDATE churches SET faith='Christian', landmark_type='church',
        tradition='Protestant'
    WHERE country='NG' AND faith='Hindu' AND taxonomy_id=3
""")
n = db.total_changes
print(f'  Hindu(tax=3)→Christian: {n}')
total_fixed += n

db.execute("""
    UPDATE churches SET faith='Christian', landmark_type='church'
    WHERE country='NG' AND faith='Hindu'
""")
n = db.total_changes
print(f'  Hindu(other)→Christian: {n}')
total_fixed += n

# Verify remaining Hindu
h = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND faith='Hindu'").fetchone()[0]
print(f'  Remaining Hindu: {h}')

# Fix the 2 Sikh gurdwaras — likely real (Indian diaspora in Lagos)
# but if not, they'd be obvious. Keep for now since names are authentic.

# Fix the remaining Other entries
print('\nFixing remaining Other entries...')
db.execute("""
    UPDATE churches SET faith='Christian', taxonomy_id=2, landmark_type='church'
    WHERE country='NG' AND faith='Other' AND taxonomy_id=553
""")
print(f'  Other(tax=553 Rabbinic)→Christian: {db.total_changes}')
db.execute("""
    UPDATE churches SET faith='Christian', taxonomy_id=2, landmark_type='church'
    WHERE country='NG' AND faith='Other' AND taxonomy_id=6
""")
print(f'  Other(tax=6 generic)→Christian: {db.total_changes}')

db.commit()

print(f'\nTotal fixed: {total_fixed}')

# Final state
print('\n=== Final Nigeria faith distribution ===')
for r in db.execute("""
    SELECT faith, COUNT(*) n FROM churches WHERE country='NG' 
    GROUP BY faith ORDER BY n DESC
"""):
    print(f'  {r[0]}: {r[1]:,}')

# Remaining anomalies
print('\n=== Remaining non-Christian, non-Islam in NG ===')
for r in db.execute("""
    SELECT faith, taxonomy_id, name, landmark_type, source, state
    FROM churches WHERE country='NG' AND faith NOT IN ('Christian','Islam')
    ORDER BY faith, taxonomy_id
"""):
    tname = db.execute("SELECT name FROM taxonomy WHERE id=?", [r[1]]).fetchone()
    tname = tname[0] if tname else '?'
    print(f'  [{r["faith"]}] tax={r[1]} {tname} | {r["name"][:50]} | type={r["landmark_type"]} | state={r["state"]} | src={r["source"]}')

db.close()
print('\nDone.')

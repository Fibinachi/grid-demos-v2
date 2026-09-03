"""Enforce taxonomy cascade across entire DB:
   denomination -> tradition -> legacy -> faith
   If a lower level is set, all higher levels must be.
"""
import sqlite3
from datetime import datetime

db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
db.execute('PRAGMA busy_timeout=60000')

CHUNK = 5000

# ── Build lookup tables from existing data ──
print('Building lookup tables from existing data...')

# tradition -> legacy mapping (most common legacy per tradition)
trad_to_legacy = {}
cur = db.execute("""
    SELECT tradition, legacy, COUNT(*) as cnt
    FROM churches
    WHERE tradition IS NOT NULL AND tradition != ''
      AND legacy IS NOT NULL AND legacy != ''
    GROUP BY tradition, legacy
    ORDER BY tradition, cnt DESC
""")
for r in cur.fetchall():
    if r[0] not in trad_to_legacy:
        trad_to_legacy[r[0]] = r[1]
print(f'  tradition->legacy: {len(trad_to_legacy)} mappings')

# tradition -> faith mapping
trad_to_faith = {}
cur = db.execute("""
    SELECT tradition, faith, COUNT(*) as cnt
    FROM churches
    WHERE tradition IS NOT NULL AND tradition != ''
      AND faith IS NOT NULL AND faith != ''
    GROUP BY tradition, faith
    ORDER BY tradition, cnt DESC
""")
for r in cur.fetchall():
    if r[0] not in trad_to_faith:
        trad_to_faith[r[0]] = r[1]
print(f'  tradition->faith: {len(trad_to_faith)} mappings')

# legacy -> faith mapping
legacy_to_faith = {}
cur = db.execute("""
    SELECT legacy, faith, COUNT(*) as cnt
    FROM churches
    WHERE legacy IS NOT NULL AND legacy != ''
      AND faith IS NOT NULL AND faith != ''
    GROUP BY legacy, faith
    ORDER BY legacy, cnt DESC
""")
for r in cur.fetchall():
    if r[0] not in legacy_to_faith:
        legacy_to_faith[r[0]] = r[1]
print(f'  legacy->faith: {len(legacy_to_faith)} mappings')

# denomination -> tradition mapping
denom_to_trad = {}
cur = db.execute("""
    SELECT denomination, tradition, COUNT(*) as cnt
    FROM churches
    WHERE denomination IS NOT NULL AND denomination != ''
      AND tradition IS NOT NULL AND tradition != ''
    GROUP BY denomination, tradition
    ORDER BY denomination, cnt DESC
""")
for r in cur.fetchall():
    if r[0] not in denom_to_trad:
        denom_to_trad[r[0]] = r[1]
print(f'  denomination->tradition: {len(denom_to_trad)} mappings')

# Also add known defaults for common traditions
known_defaults = {
    'Catholic': {'legacy': 'Catholic', 'faith': 'christian'},
    'Catholic Churches': {'legacy': 'Catholic', 'faith': 'christian'},
    'Roman Catholic': {'legacy': 'Catholic', 'faith': 'christian'},
    'Anglican': {'legacy': 'Anglican', 'faith': 'christian'},
    'Anglican Churches': {'legacy': 'Anglican', 'faith': 'christian'},
    'Episcopal and Anglican Churches': {'legacy': 'Anglican', 'faith': 'christian'},
    'Orthodox': {'legacy': 'Orthodox', 'faith': 'christian'},
    'Baptist': {'legacy': 'Baptist', 'faith': 'christian'},
    'Baptist Churches': {'legacy': 'Baptist', 'faith': 'christian'},
    'Evangelical': {'legacy': 'Evangelical', 'faith': 'christian'},
    'Pentecostal': {'legacy': 'Pentecostal', 'faith': 'christian'},
    'Pentecostal Churches': {'legacy': 'Pentecostal', 'faith': 'christian'},
    'Lutheran': {'legacy': 'Lutheran', 'faith': 'christian'},
    'Methodist': {'legacy': 'Methodist', 'faith': 'christian'},
    'Methodist Churches': {'legacy': 'Methodist', 'faith': 'christian'},
    'Presbyterian': {'legacy': 'Presbyterian', 'faith': 'christian'},
    'Presbyterian Churches': {'legacy': 'Presbyterian', 'faith': 'christian'},
    'Churches of Christ': {'legacy': 'Churches of Christ', 'faith': 'christian'},
    'LDS': {'legacy': 'Latter-day Saints', 'faith': 'christian'},
    'Mormon': {'legacy': 'Latter-day Saints', 'faith': 'christian'},
    'Jehovah Witnesses': {'legacy': 'Jehovah\'s Witnesses', 'faith': 'christian'},
    'Holiness Churches': {'legacy': 'Protestant', 'faith': 'christian'},
    'Adventist': {'legacy': 'Adventist', 'faith': 'christian'},
    'Reformed': {'legacy': 'Reformed', 'faith': 'christian'},
    'Protestant': {'legacy': 'Protestant', 'faith': 'christian'},
    'Muslim': {'legacy': 'Muslim', 'faith': 'muslim'},
    'Sunni': {'legacy': 'Muslim', 'faith': 'muslim'},
    'Shia': {'legacy': 'Muslim', 'faith': 'muslim'},
    'Jewish': {'legacy': 'Jewish', 'faith': 'jewish'},
    'Hindu': {'legacy': 'Hindu', 'faith': 'hindu'},
    'Buddhist': {'legacy': 'Buddhist', 'faith': 'buddhist'},
    'Sikh': {'legacy': 'Sikh', 'faith': 'sikh'},
    'Bahai': {'legacy': 'Bahai', 'faith': 'bahai'},
}

# Fill in any missing from defaults
for trad, vals in known_defaults.items():
    if trad not in trad_to_legacy and 'legacy' in vals:
        trad_to_legacy[trad] = vals['legacy']
    if trad not in trad_to_faith and 'faith' in vals:
        trad_to_faith[trad] = vals['faith']

print(f'  After defaults: tradition->legacy: {len(trad_to_legacy)}, tradition->faith: {len(trad_to_faith)}')

# ── Step 1: Fix tradition -> legacy -> faith (89,714 + 14,632 violations) ──
print('\nFixing tradition cascade (tradition set, missing legacy/faith)...')

# Get all distinct traditions that are missing legacy or faith
cur = db.execute("""
    SELECT DISTINCT tradition FROM churches
    WHERE (tradition IS NOT NULL AND tradition != '')
      AND ((legacy IS NULL OR legacy = '') OR (faith IS NULL OR faith = ''))
""")
traditions_to_fix = [r[0] for r in cur.fetchall()]
print(f'  {len(traditions_to_fix)} distinct traditions to fix')

fixed_trad_legacy = 0
fixed_trad_faith = 0
for trad in traditions_to_fix:
    legacy = trad_to_legacy.get(trad)
    faith = trad_to_faith.get(trad)
    
    if legacy:
        db.execute("""
            UPDATE churches SET legacy = ? 
            WHERE tradition = ? AND (legacy IS NULL OR legacy = '')
        """, (legacy, trad))
        fixed_trad_legacy += db.execute("SELECT changes()").fetchone()[0]
    
    if faith:
        db.execute("""
            UPDATE churches SET faith = ? 
            WHERE tradition = ? AND (faith IS NULL OR faith = '')
        """, (faith, trad))
        fixed_trad_faith += db.execute("SELECT changes()").fetchone()[0]

db.commit()
print(f'  Updated {fixed_trad_legacy} entries with legacy')
print(f'  Updated {fixed_trad_faith} entries with faith')

# ── Step 2: Fix legacy -> faith (183 violations) ──
print('\nFixing legacy cascade (legacy set, missing faith)...')

cur = db.execute("""
    SELECT DISTINCT legacy FROM churches
    WHERE (legacy IS NOT NULL AND legacy != '')
      AND (faith IS NULL OR faith = '')
""")
legacies_to_fix = [r[0] for r in cur.fetchall()]
print(f'  {len(legacies_to_fix)} distinct legacies to fix')

fixed_legacy_faith = 0
for leg in legacies_to_fix:
    faith = legacy_to_faith.get(leg)
    if not faith:
        # Try known defaults
        legacy_lower = leg.lower()
        if 'catholic' in legacy_lower or 'roman' in legacy_lower:
            faith = 'christian'
        elif 'baptist' in legacy_lower or 'methodist' in legacy_lower or 'lutheran' in legacy_lower:
            faith = 'christian'
        elif 'muslim' in legacy_lower or 'islam' in legacy_lower:
            faith = 'muslim'
        elif 'jewish' in legacy_lower or 'judaism' in legacy_lower:
            faith = 'jewish'
        elif 'hindu' in legacy_lower:
            faith = 'hindu'
        elif 'budd' in legacy_lower:
            faith = 'buddhist'
        elif 'sikh' in legacy_lower:
            faith = 'sikh'
        elif 'bahai' in legacy_lower:
            faith = 'bahai'
        else:
            faith = 'christian'  # safest default
    
    if faith:
        db.execute("""
            UPDATE churches SET faith = ? 
            WHERE legacy = ? AND (faith IS NULL OR faith = '')
        """, (faith, leg))
        fixed_legacy_faith += db.execute("SELECT changes()").fetchone()[0]

db.commit()
print(f'  Updated {fixed_legacy_faith} entries with faith')

# ── Step 3: Fix denomination -> tradition -> legacy -> faith (88 violations) ──
print('\nFixing denomination cascade (denomination set, missing parent levels)...')

# First fix missing tradition from denomination
denom_fixed_trad = 0
cur = db.execute("""
    SELECT DISTINCT denomination FROM churches
    WHERE (denomination IS NOT NULL AND denomination != '')
      AND (tradition IS NULL OR tradition = '')
""")
for r in cur.fetchall():
    denom = r[0]
    trad = denom_to_trad.get(denom)
    if trad:
        db.execute("""
            UPDATE churches SET tradition = ? 
            WHERE denomination = ? AND (tradition IS NULL OR tradition = '')
        """, (trad, denom))
        denom_fixed_trad += db.execute("SELECT changes()").fetchone()[0]

db.commit()

# Then fix missing legacy from denominations (tradition now set from step above)
denom_fixed_legacy = 0
cur = db.execute("""
    SELECT DISTINCT denomination FROM churches
    WHERE (denomination IS NOT NULL AND denomination != '')
      AND (legacy IS NULL OR legacy = '')
""")
for r in cur.fetchall():
    denom = r[0]
    # Get the tradition for this denom
    trad_row = db.execute("""
        SELECT tradition FROM churches 
        WHERE denomination = ? AND tradition IS NOT NULL AND tradition != ''
        LIMIT 1
    """, (denom,)).fetchone()
    if trad_row:
        trad = trad_row[0]
        legacy = trad_to_legacy.get(trad)
        if legacy:
            db.execute("""
                UPDATE churches SET legacy = ? 
                WHERE denomination = ? AND (legacy IS NULL OR legacy = '')
            """, (legacy, denom))
            denom_fixed_legacy += db.execute("SELECT changes()").fetchone()[0]

db.commit()
print(f'  Updated {denom_fixed_trad} entries with tradition')
print(f'  Updated {denom_fixed_legacy} entries with legacy')

# ── Verify ──
print('\n=== Verification ===')
v1 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (denomination IS NOT NULL AND denomination != '')
      AND (tradition IS NULL OR tradition = '')""").fetchone()[0]
v2 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (denomination IS NOT NULL AND denomination != '')
      AND (legacy IS NULL OR legacy = '')""").fetchone()[0]
v3 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (denomination IS NOT NULL AND denomination != '')
      AND (faith IS NULL OR faith = '')""").fetchone()[0]
v4 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (tradition IS NOT NULL AND tradition != '')
      AND (legacy IS NULL OR legacy = '')""").fetchone()[0]
v5 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (tradition IS NOT NULL AND tradition != '')
      AND (faith IS NULL OR faith = '')""").fetchone()[0]
v6 = db.execute("""SELECT COUNT(*) FROM churches
    WHERE (legacy IS NOT NULL AND legacy != '')
      AND (faith IS NULL OR faith = '')""").fetchone()[0]

print(f'  Denom set, tradition missing: {v1}')
print(f'  Denom set, legacy missing:    {v2}')
print(f'  Denom set, faith missing:     {v3}')
print(f'  Tradition set, legacy missing: {v4}')
print(f'  Tradition set, faith missing:  {v5}')
print(f'  Legacy set, faith missing:     {v6}')

# Log
now = datetime.now().isoformat()
db.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                churches_updated, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", ('taxonomy_cascade', '_fix_taxonomy_cascade.py', now, now,
      fixed_trad_legacy + fixed_trad_faith + fixed_legacy_faith + denom_fixed_trad + denom_fixed_legacy,
      'faith,legacy,tradition,denomination', 'completed',
      f'Fixed: trad->legacy={fixed_trad_legacy}, trad->faith={fixed_trad_faith}, legacy->faith={fixed_legacy_faith}, denom->trad={denom_fixed_trad}, denom->legacy={denom_fixed_legacy}'))
db.commit()

db.close()
print('\nDone!')

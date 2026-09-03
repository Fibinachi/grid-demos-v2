"""
Second-pass cleanup of LDS names after initial normalization.
Fixes edge cases the first pass missed or got wrong.
"""
import sqlite3, re
from datetime import datetime

DB = r'E:\grid\churches.db'
CANONICAL = 'The Church of Jesus Christ of Latter-day Saints'
SPANISH_CANONICAL = 'La Iglesia de Jesucristo de los Santos de los Últimos Días'

db = sqlite3.connect(DB, timeout=120)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()
now = datetime.now().isoformat()

lds_ids = (17,166,167,168,169,170,171,172,458,459,460,585,586,587,588,589,590,591,592,593,594,595,596)
ph = ','.join('?' for _ in lds_ids)

fixes = []

# ── Fix 1: Spanish "La" suffix (324 entries) ──
# "La Iglesia de Jesucristo de los Santos de los Últimos Días — La" → remove "— La"
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = ? AND taxonomy_id IN ({ph})""", 
    (SPANISH_CANONICAL + ' \u2014 La',) + lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (SPANISH_CANONICAL, SPANISH_CANONICAL + ' \u2014 La') + lds_ids)
    fixes.append(('Spanish "La" suffix removed', cnt))
    print(f'  Fixed Spanish "La" suffix: {cnt} entries')

# ── Fix 2: Spanish without accent marks ──
# "Iglesia de Jesucristo de los Santos de los Ultimos Días" → canonical (with accents)
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Iglesia de Jesucristo de los Santos de los Ultimos Días' 
    AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (SPANISH_CANONICAL, 'Iglesia de Jesucristo de los Santos de los Ultimos Días') + lds_ids)
    fixes.append(('Spanish accent fix', cnt))
    print(f'  Fixed Spanish accent: {cnt} entries')

# ── Fix 3: "Templo Mormon" → canonical Spanish ──
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Templo Mormon' AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (SPANISH_CANONICAL, 'Templo Mormon') + lds_ids)
    fixes.append(('Templo Mormon', cnt))
    print(f'  Fixed Templo Mormon: {cnt} entries')

# ── Fix 4: "Church - Jesus Christ - Lds" → canonical ──
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Church - Jesus Christ - Lds' AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (CANONICAL, 'Church - Jesus Christ - Lds') + lds_ids)
    fixes.append(('Church - Jesus Christ - Lds', cnt))
    print(f'  Fixed Church - Jesus Christ - Lds: {cnt} entries')

# ── Fix 5: "Church of Jesus Christ of Latter-day Saints Church" → canonical ──
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Church of Jesus Christ of Latter-day Saints Church' AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (CANONICAL, 'Church of Jesus Christ of Latter-day Saints Church') + lds_ids)
    fixes.append(('Church of Jesus Christ of Latter-day Saints Church', cnt))
    print(f'  Fixed double-Church: {cnt} entries')

# ── Fix 6: "Church Of Latter Day Saints" → canonical ──
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Church Of Latter Day Saints' AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (CANONICAL, 'Church Of Latter Day Saints') + lds_ids)
    fixes.append(('Church Of Latter Day Saints', cnt))
    print(f'  Fixed Church Of Latter Day Saints: {cnt} entries')

# ── Fix 7: "Mormon" standalone → canonical ──
c.execute(f"""SELECT COUNT(*) FROM churches 
    WHERE name = 'Mormon' AND taxonomy_id IN ({ph})""", lds_ids)
cnt = c.fetchone()[0]
if cnt:
    c.execute(f"""UPDATE churches SET name = ? 
        WHERE name = ? AND taxonomy_id IN ({ph})""",
        (CANONICAL, 'Mormon') + lds_ids)
    fixes.append(('Mormon standalone', cnt))
    print(f'  Fixed Mormon standalone: {cnt} entries')

# ── Fix 8: "LDS Stake Center" with bad extracted location ──
# Fix entries like "LDS Stake Center — Church Of Jesus Christ Of"
# and "LDS Seminary — Church Of Jesus Christ Of"
for prefix, type_name in [('LDS Stake Center', 'stake_house'), 
                           ('LDS Seminary', 'seminary'),
                           ('LDS Institute of Religion', 'institute')]:
    c.execute(f"""SELECT name, COUNT(*) FROM churches 
        WHERE name LIKE ? AND taxonomy_id IN ({ph})
        GROUP BY name""", (f'{prefix} %',) + lds_ids)
    for name, cnt in c.fetchall():
        suffix = name[len(prefix):].strip().lstrip('\u2014-–, ').strip()
        low_suffix = suffix.lower()
        # If the extracted location is a church name fragment, use city/state instead
        if any(kw in low_suffix for kw in ['church of jesus christ', 'church of latter', 
                                              'latter-day saint', 'latter day saint',
                                              'church of jesus']):
            # Get city/state from lds_hierarchy
            c.execute(f"""SELECT h.city, h.state FROM lds_hierarchy h
                JOIN churches c2 ON h.church_id = c2.id
                WHERE c2.name = ? AND c2.taxonomy_id IN ({ph})
                LIMIT 1""", (name,) + lds_ids)
            row = c.fetchone()
            if row and row[0] and row[0] != 'None':
                loc = row[0]
                if row[1] and row[1] != 'None':
                    loc += f', {row[1]}'
                new_name = f'{prefix} \u2014 {loc}'
            else:
                new_name = prefix  # Drop the bad suffix
            
            c.execute(f"""UPDATE churches SET name = ?
                WHERE name = ? AND taxonomy_id IN ({ph})""",
                (new_name, name) + lds_ids)
            fixes.append((f'{type_name} bad location fix: {suffix[:40]}', cnt))
            print(f'  Fixed {type_name}: "{suffix[:50]}" -> "{new_name[len(prefix)+3:]}" ({cnt} entries)')

# ── Fix 9: "LDS Employment Resource Center" with bad location ──
c.execute(f"""SELECT name, COUNT(*) FROM churches 
    WHERE name LIKE 'LDS Employment Resource Center %' AND taxonomy_id IN ({ph})
    GROUP BY name""", lds_ids)
for name, cnt in c.fetchall():
    suffix = name[len('LDS Employment Resource Center'):].strip().lstrip('\u2014-–, ').strip()
    low_suffix = suffix.lower()
    if any(kw in low_suffix for kw in ['church of jesus', 'latter-day saint', 'latter day saint']):
        c.execute(f"""SELECT h.city, h.state FROM lds_hierarchy h
            JOIN churches c2 ON h.church_id = c2.id
            WHERE c2.name = ? AND c2.taxonomy_id IN ({ph})
            LIMIT 1""", (name,) + lds_ids)
        row = c.fetchone()
        if row and row[0] and row[0] != 'None':
            loc = row[0]
            if row[1] and row[1] != 'None' and row[1] not in loc:
                loc += f', {row[1]}'
            new_name = f'LDS Employment Resource Center \u2014 {loc}'
        else:
            new_name = 'LDS Employment Resource Center'
        
        c.execute(f"""UPDATE churches SET name = ?
            WHERE name = ? AND taxonomy_id IN ({ph})""",
            (new_name, name) + lds_ids)
        fixes.append((f'employment_center bad location fix', cnt))
        print(f'  Fixed employment center: "{suffix[:50]}" -> "{new_name}" ({cnt} entries)')

db.commit()

# ── Log enrichment changes ──
total_fixed = sum(f[1] for f in fixes)
print(f'\nTotal fixed: {total_fixed} entries across {len(fixes)} fix types')

# Log provenance for this second pass
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
                                 churches_updated, fields_populated, records_attempted, status)
    VALUES ('lds_name_normalizer_pass2', 'standardize_lds_names.py', ?, ?, ?, 'name', ?, 'completed')
""", (now, datetime.now().isoformat(), total_fixed, total_fixed))
db.commit()

# ── Final stats ──
c.execute(f'SELECT COUNT(DISTINCT name) FROM churches WHERE taxonomy_id IN ({ph})', lds_ids)
final_unique = c.fetchone()[0]
print(f'Unique LDS names: {final_unique:,}')
print('Done.')
db.close()

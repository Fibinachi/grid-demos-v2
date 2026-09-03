"""
Fix Lutheran: merge LCMS duplicates, backfill all unclassified "Lutheran" churches.
"""
import sqlite3

DB_PATH = r'E:\grid\churches.db'
db = sqlite3.connect(DB_PATH)
db.execute('PRAGMA busy_timeout=60000')
db.execute('PRAGMA journal_mode=WAL')
c = db.cursor()

# Get IDs
lutheran_trad = c.execute("SELECT id FROM tradition WHERE name='Lutheran'").fetchone()[0]
lutheran_legacy = c.execute("SELECT id FROM legacy WHERE name='Protestant'").fetchone()[0]
lutheran_other_mov = c.execute("SELECT id FROM movement WHERE name='Lutheran (Other)'").fetchone()[0]
lcms_mov = c.execute("SELECT id FROM movement WHERE name='Lutheran Church - Missouri Synod'").fetchone()[0]

print('=== STEP 1: Merge LCMS duplicates ===')
lcms_dupes = [
    'Lutheran Church Missouri Synod',
    'Lutheran Church--Missouri Synod',
]
for dup_name in lcms_dupes:
    dup = c.execute("SELECT id FROM movement WHERE name=?", (dup_name,)).fetchone()
    if dup:
        n = c.execute("UPDATE churches SET movement_id=? WHERE movement_id=?", 
                      (lcms_mov, dup[0])).rowcount
        c.execute("DELETE FROM movement WHERE id=?", (dup[0],))
        print(f'  Merged {dup_name} ({n} churches) → LCMS')

# Also merge ELCA duplicates
elca_mov = c.execute("SELECT id FROM movement WHERE name='Evangelical Lutheran Church in America'").fetchone()
if elca_mov:
    elca_mov = elca_mov[0]
    elca_dup = c.execute("SELECT id FROM movement WHERE name='ELCA'").fetchone()
    if elca_dup:
        n = c.execute("UPDATE churches SET movement_id=? WHERE movement_id=?", 
                      (elca_mov, elca_dup[0])).rowcount
        c.execute("DELETE FROM movement WHERE id=?", (elca_dup[0],))
        print(f'  Merged ELCA ({n} churches) → Evangelical Lutheran Church in America')

db.commit()

print()
print('=== STEP 2: Backfill all unclassified Lutheran churches ===')

# Pattern-based movement assignment for unclassified Lutherans
# ELCA patterns
elca_n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND movement_id IS NULL
    AND name LIKE '%Lutheran%'
    AND name LIKE '%Evangelical Lutheran Church in America%'
""", (elca_mov, lutheran_trad, lutheran_legacy)).rowcount

# LCMS patterns
lcms_n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND movement_id IS NULL
    AND name LIKE '%Lutheran%'
    AND name LIKE '%Lutheran Church - Missouri%'
""", (lcms_mov, lutheran_trad, lutheran_legacy)).rowcount

# WELS patterns
wels_mov = c.execute("SELECT id FROM movement WHERE name='Wisconsin Evangelical Lutheran Synod'").fetchone()
if wels_mov:
    wels_n = c.execute("""
        UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
        landmark_type=COALESCE(landmark_type, 'church')
        WHERE faith='Christian' AND movement_id IS NULL
        AND name LIKE '%Lutheran%'
        AND name LIKE '%Wisconsin%'
    """, (wels_mov[0], lutheran_trad, lutheran_legacy)).rowcount
else:
    wels_n = 0

# ELCIC (Canada)
elcic_n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND movement_id IS NULL
    AND name LIKE '%Lutheran%'
    AND name LIKE '%Evangelical Lutheran Church in Canada%'
""", (lutheran_other_mov, lutheran_trad, lutheran_legacy)).rowcount

# Remaining: tag as Lutheran (Other)
other_n = c.execute("""
    UPDATE churches SET movement_id=?, tradition_id=?, legacy_id=?,
    landmark_type=COALESCE(landmark_type, 'church')
    WHERE faith='Christian' AND movement_id IS NULL
    AND name LIKE '%Lutheran%'
""", (lutheran_other_mov, lutheran_trad, lutheran_legacy)).rowcount

db.commit()

print(f'  ELCA: {elca_n}')
print(f'  LCMS: {lcms_n}')
print(f'  WELS: {wels_n}')
print(f'  ELCIC (Canada): {elcic_n}')
print(f'  Lutheran (Other): {other_n}')
print(f'  TOTAL backfilled: {elca_n + lcms_n + wels_n + elcic_n + other_n}')

# Verify
rem = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Christian' AND name LIKE '%Lutheran%' AND movement_id IS NULL
""").fetchone()[0]
print(f'\n  Remaining unclassified Lutheran: {rem}')

# Final totals
for mv_name in ['Evangelical Lutheran Church in America', 'Lutheran Church - Missouri Synod', 
                'Wisconsin Evangelical Lutheran Synod', 'Lutheran (Other)']:
    mv = c.execute("SELECT id FROM movement WHERE name=?", (mv_name,)).fetchone()
    if mv:
        n = c.execute("SELECT COUNT(*) FROM churches WHERE movement_id=?", (mv[0],)).fetchone()[0]
        print(f'  {mv_name}: {n:,}')

db.close()
print('\nDONE')

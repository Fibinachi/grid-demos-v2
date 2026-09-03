"""Classify clearly Islamic null-faith entries (Arabic names in Muslim-majority countries)."""
import sqlite3, re

DB = "E:\\grid\\churches.db"
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()

# Arabic mosque/shrine keywords
ARABIC_PATTERNS = [
    ('مسجد', 'mosque'),
    ('جامع', 'grand_mosque'),
    ('مصلى', 'prayer_hall'),
    ('دار الحديث', 'dar_hadith'),
    ('دار القرآن', 'dar_quran'),
    ('دار العلم', 'dar_ilm'),
    ('مكة', 'mecca_ref'),
    ('الكعبة', 'kabba_ref'),
    ('الحرم', 'haram_ref'),
    ('الإسلام', 'islam_ref'),
    ('الإحسان', 'ihsan'),
    ('الفرقان', 'furqan'),
    ('التقوى', 'taqwa'),
    ('السلام', 'salam'),
    ('الرحمن', 'rahman'),
    ('الرحيم', 'rahim'),
    ('القدس', 'quds'),
    ('المدينة', 'madina'),
    ('الضالع', 'daleh'),
    ('الصدف', 'sadaf'),
]

# Muslim-majority countries where OSM "shrine" entries are almost certainly Islamic
MUSLIM_COUNTRIES = {
    'SA','YE','IQ','IR','SY','JO','LB','PS','EG','LY','TN','DZ','MA',
    'SD','SO','DJ','MR','ER','TD','NE','ML','SN','GN','BF','NG',
    'AF','PK','BD','OM','AE','QA','BH','KW','TR','AZ','UZ','TM','TJ','KG','KZ',
    'ID','MY','BN','MV','DZ','EH','GM','SL','LR','CI','GH','TG','BJ',
}

# Also: countries with >= 50% Muslim population
MUSLIM_MAJORITY_50 = {
    'AL','XK','BA','EH','GM','SL','CI','GH','TG','BJ','ET','KE','TZ','MW','MZ',
    'UG','CM','GA','CG','DJ'
}

ALL_MUSLIM_COUNTRIES = MUSLIM_COUNTRIES | MUSLIM_MAJORITY_50

null_start = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
print(f"Starting null faith: {null_start:,}")

# --- Phase 1: Arabic mosque/shrine keywords in any country ---
total_phase1 = 0
for pattern, label in ARABIC_PATTERNS:
    c.execute(
        "UPDATE churches SET faith='Islam' WHERE (faith IS NULL OR faith = '') AND name LIKE ?",
        (f'%{pattern}%',)
    )
    count = c.rowcount
    if count:
        print(f"  {label}: {count:,}")
        total_phase1 += count
conn.commit()
print(f"Phase 1 (Arabic keywords): {total_phase1:,}")

# --- Phase 2: All remaining null-faith in Muslim-majority countries with landmark_type='shrine' ---
c.execute("""
    UPDATE churches SET faith='Islam'
    WHERE (faith IS NULL OR faith = '')
    AND country IN ({})
    AND landmark_type IN ('shrine', 'mosque', 'musallah', 'tomb', 'mausoleum', 'cemetery', 'grave')
""".format(','.join(f"'{c}'" for c in sorted(ALL_MUSLIM_COUNTRIES))))
phase2 = c.rowcount
print(f"Phase 2 (Muslim country + Islamic landmark): {phase2:,}")
conn.commit()

# --- Phase 3: All remaining null-faith landmark_type='mosque' globally ---
c.execute("""
    UPDATE churches SET faith='Islam'
    WHERE (faith IS NULL OR faith = '')
    AND landmark_type = 'mosque'
""")
phase3 = c.rowcount
print(f"Phase 3 (landmark=mosque globally): {phase3:,}")
conn.commit()

# --- Phase 4: All remaining null-faith landmark_type='shrine' in North Africa / Middle East ---
MIDDLE_EAST = {'SA','YE','IQ','IR','SY','JO','LB','PS','EG','LY','TN','DZ','MA','SD','SO','AE','QA','BH','KW','OM'}
c.execute("""
    UPDATE churches SET faith='Islam'
    WHERE (faith IS NULL OR faith = '')
    AND country IN ({})
    AND landmark_type = 'shrine'
""".format(','.join(f"'{c}'" for c in MIDDLE_EAST)))
phase4 = c.rowcount
print(f"Phase 4 (ME/NA shrine remaining): {phase4:,}")
conn.commit()

# --- Summary ---
null_end = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
total_isl = c.execute("SELECT COUNT(*) FROM churches WHERE faith = 'Islam'").fetchone()[0]
print(f"\nRemaining null faith: {null_end:,}")
print(f"Total Islam entries: {total_isl:,}")
print(f"Classified by this script: {null_start - null_end:,}")

# Log provenance
classified = null_start - null_end
if classified > 0:
    c.execute(
        "INSERT INTO provenance_log (script_name, churches_updated, churches_inserted, notes, completed_at, status, fields_populated) VALUES (?, ?, 0, ?, datetime('now'), 'completed', 'faith')",
        ('_classify_null_islam', classified, f"Classified {classified} Arabic-named / Muslim-country null-faith entries as Islam")
    )
    conn.commit()

conn.close()

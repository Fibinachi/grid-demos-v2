"""
Phase 1: Normalize faith values
Fix case, synonyms, and mis-tagged faith values across ALL records.
"""
import sqlite3, sys
from datetime import datetime

CHUNK = 500
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# ===== Step 1: Map messy faith values to canonical =====
faith_fixes = {
    # Lowercase → Capitalized
    'christian': 'Christian',
    'hindu': 'Hindu',
    'buddhist': 'Buddhist',
    'jewish': 'Judaism',
    'shinto': 'Shinto',
    'taoist': 'Taoist',
    'sikh': 'Sikh',
    'muslim': 'Islam',
    'bahai': "Baháʼí",
    'jain': 'Jain',
    'pagan': 'Pagan',
    'animist': 'Animist',
    'zoroastrian': 'Zoroastrian',
    'confucian': 'Confucian',
    # Synonyms → canonical faith
    'synagogue': 'Judaism',
    'jewish_org': 'Judaism',
    'jewish org': 'Judaism',
    'islam': 'Islam',
    'judaism': 'Judaism',
    # Christian miscategorizations
    'roman catholic': 'Christian',
    'catholic': 'Christian',
    'orthodox': 'Christian',
    'protestant': 'Christian',
    'anglican': 'Christian',
    'lutheran': 'Christian',
    'methodist': 'Christian',
    'baptist': 'Christian',
    'presbyterian': 'Christian',
    'pentecostal': 'Christian',
    'evangelical': 'Christian',
    'mormon': 'Christian',
    'lds': 'Christian',
    'jehovah': 'Christian',
    'jehovah\'s witness': 'Christian',
    'jw': 'Christian',
    'seventh-day adventist': 'Christian',
    'adventist': 'Christian',
    'church of christ': 'Christian',
    'church of god': 'Christian',
    'coptic': 'Christian',
    'assyrian': 'Christian',
    'maronite': 'Christian',
    'chaldean': 'Christian',
    'syriac': 'Christian',
    'armenian': 'Christian',
    'quaker': 'Christian',
    'friends': 'Christian',
    'united church of christ': 'Christian',
    'congregational': 'Christian',
    'disciples of christ': 'Christian',
    'nazarene': 'Christian',
    'salvation army': 'Christian',
    'unitarian': 'Christian',
    'universalist': 'Christian',
    'united methodist': 'Christian',
    'ame': 'Christian',
    'ame zion': 'Christian',
    'cme': 'Christian',
    'holiness': 'Christian',
    'reformed': 'Christian',
    'mennonite': 'Christian',
    'amish': 'Christian',
    'brethren': 'Christian',
    'moravian': 'Christian',
    'old catholic': 'Christian',
    # Other minority faiths
    'humanist': 'Other',
    'new age': 'Other',
    'new_age': 'Other',
    'native american': 'Other',
    'indigenous': 'Other',
    'unitarian universalist': 'Other',
    'caodaism': 'Other',
    'tenrikyo': 'Other',
    'scientology': 'Other',
    'rastafari': 'Other',
    'rastafarian': 'Other',
    'druid': 'Other',
    'wiccan': 'Other',
    'wicca': 'Pagan',
    'heathen': 'Pagan',
    'asatru': 'Pagan',
    'shamanism': 'Animist',
    'unaffiliated': '',
    'none': '',
    'unknown': '',
}

print("Step 1: Normalizing faith values...")
total = 0
for old_val, new_val in faith_fixes.items():
    c.execute("UPDATE churches SET faith=? WHERE LOWER(faith)=?", (new_val, old_val))
    if c.rowcount:
        print(f"  {old_val:25s} → {new_val:15s} ({c.rowcount:>7,} records)")
        total += c.rowcount

# Also fix faith_tradition that's same as faith concept
print(f"\nTotal faith values corrected: {total:,}")
db.commit()

# ===== Step 2: Show remaining =====
print("\n=== Remaining faith counts ===")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NOT NULL AND faith != '' GROUP BY faith ORDER BY COUNT(*) DESC")
for r in c.fetchall():
    print(f"  {r[0]:20s} {r[1]:>8,}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"  {'NULL':20s} {c.fetchone()[0]:>8,}")

db.close()
print("\nPhase 1 complete.")

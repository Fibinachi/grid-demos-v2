"""
Phase 3: Comprehensive FLTD classifier for all non-Christian, non-Islam faiths.
Sets legacy/tradition/denomination based on country priors and name patterns.
Uses SQLite REGEXP via Python re module.
"""
import sqlite3, sys, re
from datetime import datetime

CHUNK = 500
db = sqlite3.connect('E:/grid/churches.db')
# Register REGEXP function using Python re
db.create_function('regexp', 2, lambda p, s: 1 if re.search(p, s or '') else 0)
c = db.cursor()

def progress(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ============================================================
# 1. BUDDHIST FLTD
# ============================================================
progress("=== BUDDHIST ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Buddhist' AND (legacy IS NULL OR legacy='')")
progress(f"Unclassified: {c.fetchone()[0]:,}")

# Country-based legacy assignment
country_legacy = {
    'TH': ('Theravada', 'Theravada'), 'MM': ('Theravada', 'Theravada'),
    'LA': ('Theravada', 'Theravada'), 'KH': ('Theravada', 'Theravada'),
    'LK': ('Theravada', 'Theravada'),
    'JP': ('Mahayana', 'Mahayana'), 'KR': ('Mahayana', 'Mahayana'),
    'CN': ('Mahayana', 'Chinese Buddhism'), 'TW': ('Mahayana', 'Chinese Buddhism'),
    'HK': ('Mahayana', 'Chinese Buddhism'), 'MO': ('Mahayana', 'Chinese Buddhism'),
    'VN': ('Mahayana', 'Vietnamese Buddhism'),
    'MN': ('Vajrayana', 'Tibetan Buddhism'), 'BT': ('Vajrayana', 'Tibetan Buddhism'),
}
for cc, (leg, trad) in country_legacy.items():
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Buddhist' AND (legacy IS NULL OR legacy='') AND country=?", (leg, trad, cc))
    progress(f"  {cc}: {c.rowcount:>6,} → {leg}/{trad}")

# Name-based refinement
name_rules = [
    (r'(?i)\bzen\b', 'Mahayana', 'Zen'),
    (r'(?i)\bthi.n\b', 'Mahayana', 'Zen'),
    (r'(?i)\bpure\s*land\b', 'Mahayana', 'Pure Land'),
    (r'(?i)\bamit[ao]bha\b', 'Mahayana', 'Pure Land'),
    (r'(?i)\bnichiren\b', 'Mahayana', 'Nichiren'),
    (r'(?i)\bsokagakkai\b|\bsoka gakkai\b', 'Mahayana', 'Nichiren'),
    (r'(?i)\btendai\b|\btiantai\b', 'Mahayana', 'Tiantai/Tendai'),
    (r'(?i)\bshingon\b', 'Vajrayana', 'Shingon'),
    (r'(?i)\b(vajrayana|tantric)\b', 'Vajrayana', 'Vajrayana'),
    (r'(?i)\btibetan\b.*\b(buddh|monaster|lama|gonpa)\b', 'Vajrayana', 'Tibetan Buddhism'),
    (r'(?i)\b(lama|gonpa|rinpoche|gyalwa|kagy[uü]|nyingma|sakya|gelug|dzogchen)\b', 'Vajrayana', 'Tibetan Buddhism'),
    (r'(?i)\btheravada\b', 'Theravada', 'Theravada'),
    (r'(?i)\bvipassana\b', 'Theravada', 'Vipassana'),
    (r'(?i)\bforest\s*tradition\b', 'Theravada', 'Thai Forest Tradition'),
    (r'(?i)\bwat\b', 'Theravada', 'Theravada'),
    (r'(?i)\bvihara\b', 'Theravada', 'Theravada'),
    (r'(?i)\bbodhi\b', 'Mahayana', 'Mahayana'),
    (r'(?i)\bmaitreya\b', 'Mahayana', 'Mahayana'),
]
for pattern, leg, trad in name_rules:
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Buddhist' AND (legacy IS NULL OR legacy='') AND name REGEXP ?", (leg, trad, pattern))
    if c.rowcount:
        progress(f"  name/{pattern[:20]:20s}: {c.rowcount:>6,} → {leg}/{trad}")

# Remaining default to Mahayana/Mahayana
c.execute("UPDATE churches SET legacy='Mahayana', tradition='Mahayana' WHERE faith='Buddhist' AND (legacy IS NULL OR legacy='')")
progress(f"  default Mahayana: {c.rowcount:,}")

db.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Buddhist' AND (legacy IS NULL OR legacy='')")
progress(f"Remaining unclassified: {c.fetchone()[0]:,}")

# ============================================================
# 2. HINDU FLTD
# ============================================================
progress("\n=== HINDU ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND (legacy IS NULL OR legacy='')")
progress(f"Unclassified: {c.fetchone()[0]:,}")

# Country-based legacy
c.execute("UPDATE churches SET legacy='Shaivism', tradition='Shaivism' WHERE faith='Hindu' AND (legacy IS NULL OR legacy='') AND country='ID'")
progress(f"  ID→Shaivism: {c.rowcount:,}")

# Name-based classification
hindu_rules = [
    (r'(?i)\b(is[ck]con|hare.krishna|krishna.consciousness|srila.prabhupada)\b', 'Vaishnavism', 'ISKCON'),
    (r'(?i)\bswaminarayan\b', 'Vaishnavism', 'Swaminarayan'),
    (r'(?i)\bgaudiya\b', 'Vaishnavism', 'Gaudiya Vaishnavism'),
    (r'(?i)\bbrahma.kumar[is]\b', 'Vaishnavism', 'Brahma Kumaris'),
    (r'(?i)\bsri.vaishnava|srivaishnava|raamanuja\b', 'Vaishnavism', 'Sri Vaishnavism'),
    (r'(?i)\b(hindu.temple|venkateswara|tirupati|balaji|srinivasa)\b', 'Vaishnavism', 'Vaishnavism'),
    (r'(?i)\b(krishna|rama|vishnu|narayana|jagannath|venkatesh|sitaram|radha)\b', 'Vaishnavism', 'Vaishnavism'),
    (r'(?i)\b(shiva|shankara|rudra|ling[ae]|nataraja|parvati|ganesh)\b', 'Shaivism', 'Shaivism'),
    (r'(?i)\b(ling[aā]|mahadev|bholenath)\b', 'Shaivism', 'Shaivism'),
    (r'(?i)\b(lingayat|v.ra.aiva|kashmir.shaivism)\b', 'Shaivism', 'Shaivism'),
    (r'(?i)\b(kali|durga|devi|chamunda|shakti|ambika|bhagavati|lakshmi|saraswati|annapurna)\b', 'Shaktism', 'Shaktism'),
    (r'(?i)\barya.samaj\b', 'Other', 'Arya Samaj'),
    (r'(?i)\bsamaj\b', 'Other', 'Reform Hindu'),
    (r'(?i)\b(sathya.sai|sai.baba|brahma.kumaris|mata.amritanandamayi|sri.chinmoy|transcendental.meditation)\b', 'Other', 'Neo-Hindu'),
    (r'(?i)\bmandir\b', 'Vaishnavism', 'Vaishnavism'),
    (r'(?i)\b(asanam|yoga|ashram)\b', 'Vaishnavism', 'Vaishnavism'),
]
for pattern, leg, trad in hindu_rules:
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Hindu' AND (legacy IS NULL OR legacy='') AND name REGEXP ?", (leg, trad, pattern))
    if c.rowcount:
        progress(f"  name/{pattern[:20]:20s}: {c.rowcount:>6,} → {leg}/{trad}")

# Remaining IN/NP default to Vaishnavism
c.execute("UPDATE churches SET legacy='Vaishnavism', tradition='Vaishnavism' WHERE faith='Hindu' AND (legacy IS NULL OR legacy='') AND country IN ('IN','NP')")
progress(f"  IN/NP→Vaishnavism: {c.rowcount:,}")
# Rest default to Vaishnavism
c.execute("UPDATE churches SET legacy='Vaishnavism', tradition='Vaishnavism' WHERE faith='Hindu' AND (legacy IS NULL OR legacy='')")
progress(f"  default Vaishnavism: {c.rowcount:,}")

db.commit()

# ============================================================
# 3. SHINTO FLTD
# ============================================================
progress("\n=== SHINTO ===")
c.execute("UPDATE churches SET legacy='Shrine Shinto', tradition='Shrine Shinto' WHERE faith='Shinto' AND (legacy IS NULL OR legacy='')")
progress(f"  default Shrine Shinto: {c.rowcount:,}")
db.commit()

# ============================================================
# 4. JUDAISM FLTD
# ============================================================
progress("\n=== JUDAISM ===")

# Name-based refinement - note: faith_tradition column doesn't exist in this DB
# Jewish classification from earlier sessions used name patterns
jewish_rules = [
    (r'(?i)\b(chabad|lubavitch|770)\b', 'Rabbinic', 'Orthodox (Chabad)'),
    (r'(?i)\b(satmar|belz|gur|bobov|breslov|munkacs|stolin|skver|vizhnitz)\b', 'Rabbinic', 'Orthodox (Hasidic)'),
    (r'(?i)\byeshiva\b', 'Rabbinic', 'Orthodox (Yeshiva)'),
    (r'(?i)\b(kollel|mesivta|talmud.torah)\b', 'Rabbinic', 'Orthodox (Yeshiva)'),
    (r'(?i)\btemple\b', 'Rabbinic', 'Reform'),
    (r'(?i)\bconservative|masorti\b', 'Rabbinic', 'Conservative'),
    (r'(?i)\breform\b', 'Rabbinic', 'Reform'),
    (r'(?i)\b(sephardi|spanish.portuguese|sefardi)\b', 'Rabbinic', 'Sephardic'),
    (r'(?i)\b(mizrahi|edot.hamizrach|persian|iraqi|kurdish)\b', 'Rabbinic', 'Mizrahi'),
    (r'(?i)\breconstructionist|renewal\b', 'Rabbinic', 'Reconstructionist'),
    (r'(?i)\bhumanistic|secular.humanist\b', 'Rabbinic', 'Humanistic'),
    (r'(?i)\bkaraite\b', 'Karaite', 'Karaite'),
]
for pattern, leg, trad in jewish_rules:
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Judaism' AND (legacy IS NULL OR legacy='') AND name REGEXP ?", (leg, trad, pattern))
    if c.rowcount:
        progress(f"  name/{pattern[:20]:20s}: {c.rowcount:>6,} → {leg}/{trad}")

# Remaining default
c.execute("UPDATE churches SET legacy='Rabbinic', tradition='Rabbinic' WHERE faith='Judaism' AND (legacy IS NULL OR legacy='')")
progress(f"  default Rabbinic: {c.rowcount:,}")
db.commit()

# ============================================================
# 5. SIKH FLTD
# ============================================================
progress("\n=== SIKH ===")
c.execute("UPDATE churches SET legacy='Sikh', tradition='Khalsa' WHERE faith='Sikh' AND (legacy IS NULL OR legacy='') AND (name REGEXP ? OR name REGEXP ?)", 
          ('(?i)\\bgurdwara\\b', '(?i)\\bgurudwara\\b'))
gurdwara = c.rowcount
c.execute("UPDATE churches SET legacy='Sikh', tradition='Khalsa' WHERE faith='Sikh' AND (legacy IS NULL OR legacy='') AND (name REGEXP ? OR name REGEXP ?)",
          ('(?i)\\bkhalsa\\b', '(?i)\\bsingh\\b.*\\bsahib\\b'))
progress(f"  gurdwara/khalsa: {gurdwara + c.rowcount:,} → Sikh/Khalsa")
c.execute("UPDATE churches SET legacy='Sikh', tradition='Khalsa' WHERE faith='Sikh' AND (legacy IS NULL OR legacy='')")
progress(f"  default Khalsa: {c.rowcount:,}")
db.commit()

# ============================================================
# 6. OTHER/Baháʼí
# ============================================================
progress("\n=== BAHÁʼÍ ===")
c.execute("UPDATE churches SET legacy='Baháʼí', tradition='Baháʼí' WHERE faith='Baháʼí' AND (legacy IS NULL OR legacy='')")
progress(f"  {c.rowcount:,}")
db.commit()

# ============================================================
# 7. OTHER/Pagan
# ============================================================
progress("\n=== PAGAN ===")
pagan_rules = [
    (r'(?i)\bwicca\b', 'Wicca'),
    (r'(?i)\bdruid\b', 'Druidry'),
    (r'(?i)\bheathen\b', 'Heathenry'),
    (r'(?i)\basatru\b', 'Heathenry'),
    (r'(?i)\bnorse\b', 'Heathenry'),
]
for pattern, trad in pagan_rules:
    c.execute("UPDATE churches SET legacy='Pagan', tradition=? WHERE faith='Pagan' AND (legacy IS NULL OR legacy='') AND name REGEXP ?", (trad, pattern))
    if c.rowcount:
        progress(f"  {trad:15s}: {c.rowcount}")
c.execute("UPDATE churches SET legacy='Pagan', tradition='Pagan' WHERE faith='Pagan' AND (legacy IS NULL OR legacy='')")
progress(f"  default Pagan: {c.rowcount:,}")
db.commit()

# ============================================================
# 8. OTHER (catch-all)
# ============================================================
progress("\n=== OTHER ===")
other_rules = [
    (r'(?i)\bhumanist\b', 'Other', 'Humanist'),
    (r'(?i)\bnew.age\b', 'Other', 'New Age'),
    (r'(?i)\bunitarian.universalist\b', 'Other', 'Unitarian Universalist'),
    (r'(?i)\bunitarian\b', 'Other', 'Unitarian Universalist'),
    (r'(?i)\brastafari\b', 'Other', 'Rastafari'),
    (r'(?i)\bscientolog\b', 'Other', 'Scientology'),
    (r'(?i)\btenrikyo\b', 'Other', 'Tenrikyo'),
    (r'(?i)\bmasonic\b', 'Other', 'Masonic'),
    (r'(?i)\bfreemason\b', 'Other', 'Masonic'),
    (r'(?i)\bagnostic\b', 'Other', 'Agnostic'),
    (r'(?i)\batheist\b', 'Other', 'Atheist'),
]
for pattern, leg, trad in other_rules:
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Other' AND (legacy IS NULL OR legacy='') AND name REGEXP ?", (leg, trad, pattern))
    if c.rowcount:
        progress(f"  {trad:25s}: {c.rowcount}")
c.execute("UPDATE churches SET legacy='Other', tradition='Other' WHERE faith='Other' AND (legacy IS NULL OR legacy='')")
progress(f"  default Other: {c.rowcount:,}")
db.commit()

# ============================================================
# SUMMARY
# ============================================================
progress("\n=== SUMMARY ===")
for f in ['Buddhist', 'Hindu', 'Shinto', 'Judaism', 'Sikh', 'Other', 'Pagan', 'Baháʼí']:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,))
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=? AND legacy IS NOT NULL AND legacy != ''", (f,))
    classified = c.fetchone()[0]
    pct = classified/total*100 if total else 0
    print(f"  {f:15s}: {total:>7,} total, {classified:>7,} classified ({pct:.1f}%)")

db.close()
progress("\nPhase 3 complete!")

"""
Phase 6: Fix FLTD for newly assigned faith records that skipped the classifier
(Shinto, Christian, Other from NULL faith), and minor noise cleanup.
"""
import sqlite3, re
from datetime import datetime
db = sqlite3.connect('E:/grid/churches.db')
db.create_function('regexp', 2, lambda p, s: 1 if re.search(p, s or '') else 0)
c = db.cursor()

def progress(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ============================================================
# 1. SHINTO — classify all unclassified Shinto
# ============================================================
progress("=== SHINTO ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Shinto' AND (legacy IS NULL OR legacy='')")
progress(f"Unclassified Shinto: {c.fetchone()[0]:,}")

c.execute("UPDATE churches SET legacy='Shrine Shinto', tradition='Shrine Shinto' WHERE faith='Shinto' AND (legacy IS NULL OR legacy='')")
progress(f"  → Shrine Shinto: {c.rowcount:,}")
db.commit()

# ============================================================
# 2. CHRISTIAN — classify newly assigned Christian (no legacy)
# ============================================================
progress("\n=== CHRISTIAN (unclassified) ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (legacy IS NULL OR legacy='')")
unclassified = c.fetchone()[0]
progress(f"Unclassified Christian: {unclassified:,}")

# Country-based assignment for the unclassified
christian_country = {
    'IT': 'Catholic', 'FR': 'Catholic', 'ES': 'Catholic', 'PT': 'Catholic',
    'PL': 'Catholic', 'IE': 'Catholic', 'MT': 'Catholic', 'PH': 'Catholic',
    'BR': 'Catholic', 'MX': 'Catholic', 'CO': 'Catholic', 'AR': 'Catholic',
    'PE': 'Catholic', 'CL': 'Catholic', 'VE': 'Catholic',
    'US': 'Protestant', 'GB': 'Anglican', 'DE': 'Protestant',
    'GR': 'Orthodox', 'CY': 'Orthodox', 'RU': 'Orthodox',
    'RO': 'Orthodox', 'BG': 'Orthodox', 'RS': 'Orthodox', 'UA': 'Orthodox',
    'ET': 'Orthodox', 'ER': 'Orthodox',
}
for cc, leg in christian_country.items():
    c.execute("UPDATE churches SET legacy=?, tradition=? WHERE faith='Christian' AND (legacy IS NULL OR legacy='') AND country=?", (leg, leg, cc))
    if c.rowcount:
        progress(f"  {cc}→{leg}: {c.rowcount:,}")

# Name-based: LDS wards/stakes
c.execute("UPDATE churches SET legacy='Other', tradition='LDS' WHERE faith='Christian' AND (legacy IS NULL OR legacy='') AND (name REGEXP ? OR name REGEXP ?)",
          ('(?i)\\bward\\b.*\\bstake\\b', '(?i)\\bstake\\b.*\\bward\\b'))
if c.rowcount:
    progress(f"  LDS wards: {c.rowcount:,}")

# Anglican name patterns
c.execute("UPDATE churches SET legacy='Anglican', tradition='Anglican' WHERE faith='Christian' AND (legacy IS NULL OR legacy='') AND (name REGEXP ?)",
          ('(?i)\\bst\\.\\s*(mary|paul|john|peter|james|michael|mark|luke|andrew|george|stephen|david|thomas|joseph|nicholas|bartholomew|matthew)\\b',))
if c.rowcount:
    progress(f"  Saint names→Anglican: {c.rowcount:,}")

# Default to Protestant for remaining
c.execute("UPDATE churches SET legacy='Protestant', tradition='Protestant' WHERE faith='Christian' AND (legacy IS NULL OR legacy='')")
progress(f"  default Protestant: {c.rowcount:,}")
db.commit()

# ============================================================
# 3. BUDDHIST noise cleanup (Methodist, Pentecostal etc.)
# ============================================================
progress("\n=== BUDDHIST noise cleanup ===")
noise_legacies = ['Methodist', 'Pentecostal', 'Evangelical', 'Baptist', 'Presbyterian',
                  'Congregational', 'Churches of Christ', 'Reformed', 'Lutheran',
                  'Adventist', 'Quaker', 'Orthodox', 'Anglican']
for leg in noise_legacies:
    c.execute("UPDATE churches SET legacy='Mahayana', tradition='Mahayana' WHERE faith='Buddhist' AND legacy=?", (leg,))
    if c.rowcount:
        progress(f"  {leg}→Mahayana: {c.rowcount:,}")
db.commit()

# ============================================================
# 4. HINDU noise cleanup
# ============================================================
progress("\n=== HINDU noise cleanup ===")
for leg in noise_legacies:
    c.execute("UPDATE churches SET legacy='Vaishnavism', tradition='Vaishnavism' WHERE faith='Hindu' AND legacy=?", (leg,))
    if c.rowcount:
        progress(f"  {leg}→Vaishnavism: {c.rowcount:,}")
db.commit()

# ============================================================
# 5. JUDAISM noise cleanup
# ============================================================
progress("\n=== JUDAISM noise cleanup ===")
for leg in noise_legacies:
    c.execute("UPDATE churches SET legacy='Rabbinic', tradition='Rabbinic' WHERE faith='Judaism' AND legacy=?", (leg,))
    if c.rowcount:
        progress(f"  {leg}→Rabbinic: {c.rowcount:,}")
db.commit()

# ============================================================
# 6. ISLAM noise (Baptist, Orthodox, etc.)
# ============================================================
progress("\n=== ISLAM minor noise cleanup ===")
for leg in ['Baptist', 'Orthodox', 'Pentecostal', 'Methodist', 'Churches of Christ']:
    c.execute("UPDATE churches SET legacy='Sunni', tradition='Sunni' WHERE faith='Islam' AND legacy=?", (leg,))
    if c.rowcount:
        progress(f"  {leg}→Sunni: {c.rowcount:,}")
db.commit()

# ============================================================
# 7. OTHER noise cleanup
# ============================================================
progress("\n=== OTHER noise cleanup ===")
for leg in noise_legacies:
    c.execute("UPDATE churches SET legacy='Other', tradition='Other' WHERE faith='Other' AND legacy=?", (leg,))
    if c.rowcount:
        progress(f"  {leg}→Other: {c.rowcount:,}")
db.commit()

# ============================================================
# FINAL SUMMARY
# ============================================================
progress("\n=== FINAL FLTD COVERAGE ===")
for f in ['Christian', 'Islam', 'Hindu', 'Buddhist', 'Shinto', 'Judaism', 'Taoist', 'Sikh', 'Other', 'Pagan', 'Baháʼí']:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (f,))
    total = c.fetchone()[0]
    if total == 0: continue
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=? AND legacy IS NOT NULL AND legacy != ''", (f,))
    legacy = c.fetchone()[0]
    pct = legacy/total*100
    print(f"  {f:15s}: {legacy:>8,}/{total:<8,} ({pct:5.1f}%)")

# NULL faith check
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"  {'NULL':15s}: 0/{c.fetchone()[0]:<8,}")

db.close()
progress("Done!")

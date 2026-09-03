#!/usr/bin/env python3
"""
Audit Hindu entries outside India for mislabeling.
Checks: country distribution, suspicious names (church/mosque/Buddhist/etc),
and entries in countries with tiny Hindu populations.
"""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
cur = conn.cursor()

total = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu'").fetchone()[0]
in_india = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND country='IN'").fetchone()[0]
outside = total - in_india
print(f"Total Hindu: {total:,}")
print(f"  In India: {in_india:,}")
print(f"  Outside India: {outside:,}")
print()

# 1. Distribution outside India (top 30)
print("=" * 60)
print("Hindu entries by country (outside India, top 40)")
print("=" * 60)
for r in cur.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches WHERE faith='Hindu'
    GROUP BY country ORDER BY cnt DESC
"""):
    if r[0] != 'IN':
        print(f"  {r[0]:30s} {r[1]:>8,}")

print()

# 2. Suspicious names: Christian keywords in Hindu entries
print("=" * 60)
print("Hindu entries with Christian-sounding names")
print("=" * 60)
CHRISTIAN_PATTERNS = [
    '%church%', '%iglesia%', '%eglise%', '%kirk%', '%kirche%',
    '%jesus%', '%christ%', '%cristo%', '%cristian%',
    '%saint%', '%san%', '%santo%', '%santa%', '%st. %',
    '%pastor%', '%bishop%', '%padre%', '%father%',
    '%catholic%', '%catolico%', '%católica%',
    '%baptist%', '%bautista%', '%lutheran%', '%luterana%',
    '%methodist%', '%metodista%', '%presbyterian%', '%presbiteriana%',
    '%pentecostal%', '%anglican%', '%mission%',
    '%evangelical%', '%evangelico%', '%evangélico%',
    '%gospel%', '%jesuit%', '%parish%', '%parroquia%',
    '%abbey%', '%monastery%', '%monasterio%',
    '%chapel%', '%capilla%',
    '%mennonite%',
]
total_suspicious = 0
for pat in CHRISTIAN_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Hindu' AND country != 'IN'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {pat:30s} {r:>8,}")
        total_suspicious += r
print(f"  {'TOTAL':30s} {total_suspicious:>8,}")

print()

# 3. Show some examples
print("=" * 60)
print("Sample Christian-sounding Hindu entries (outside IN, top 30)")
print("=" * 60)
for r in cur.execute("""
    SELECT rowid, name, country, denomination, landmark_type, source
    FROM churches
    WHERE faith='Hindu' AND country != 'IN'
    AND (name LIKE '%church%' OR name LIKE '%jesus%' OR name LIKE '%christ%'
         OR name LIKE '%catholic%' OR name LIKE '%iglesia%'
         OR name LIKE '%saint%' OR name LIKE '%san%' OR name LIKE '%st. %'
         OR name LIKE '%baptist%' OR name LIKE '%lutheran%'
         OR name LIKE '%methodist%' OR name LIKE '%mission%'
         OR name LIKE '%gospel%')
    ORDER BY country
    LIMIT 30
"""):
    print(f"  rowid={r[0]:>8}  {r[1][:60]:60s}  {r[2]}  denom={r[3] or '':20s}  lm={r[4] or '':15s}  {r[5]}")

print()

# 4. Muslim-sounding names
print("=" * 60)
print("Hindu entries with Muslim-sounding names (outside IN)")
print("=" * 60)
MUSLIM_PATTERNS = [
    '%mosque%', '%masjid%', '%islamic%', '%muslim%',
    '%jami%', '%masjid%',
    '%allah%', '%muhammad%', '%quran%', '%koran%',
]
for pat in MUSLIM_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Hindu' AND country != 'IN'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {pat:30s} {r:>8,}")
print()

# 5. Buddhist-sounding names
print("=" * 60)
print("Hindu entries with Buddhist-sounding names (outside IN)")
print("=" * 60)
BUDDHIST_PATTERNS = [
    '%buddh%', '%temple%', '%pagoda%', '%wat %', '%wat_%',
    '%vihara%', '%monastery%', '%monk%',
    '%zen%', '%dharma%', '%sangha%',
]
for pat in BUDDHIST_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Hindu' AND country != 'IN'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {pat:30s} {r:>8,}")
print()

# 6. 'Temple' keyword analysis — legitimate for Hindu but check for over-tagging
print("=" * 60)
print("Hindu entries with 'temple' in name (outside IN, non-temple patterns)")
print("=" * 60)
# Legitimate Hindu-specific temple patterns
LEGIT_HINDU = ['%mandir%', '%kovil%', '%koil%', '%gudi%', '%devasthanam%',
               '%murugan%', '%ganesh%', '%shiva%', '%vishnu%', '%rama%',
               '%krishna%', '%devi%', '%durga%', '%kali%', '%lakshmi%',
               '%saraswati%', '%hanuman%', '%ayyappa%', '%sai baba%']

# Count temple entries without any Hindu-specific keywords
r = cur.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Hindu' AND country != 'IN'
    AND name LIKE '%temple%'
    AND name NOT LIKE '%mandir%'
    AND name NOT LIKE '%kovil%' AND name NOT LIKE '%koil%'
    AND name NOT LIKE '%gudi%'
    AND name NOT LIKE '%murugan%' AND name NOT LIKE '%ganesh%'
    AND name NOT LIKE '%shiva%' AND name NOT LIKE '%vishnu%'
    AND name NOT LIKE '%rama%' AND name NOT LIKE '%krishna%'
    AND name NOT LIKE '%devi%' AND name NOT LIKE '%durga%'
    AND name NOT LIKE '%kali%' AND name NOT LIKE '%lakshmi%'
    AND name NOT LIKE '%hanuman%'
""").fetchone()[0]
print(f"  Temple entries w/o Hindu deity keywords: {r:,}")

# Show some
print(f"\n  Sample entries (up to 20):")
for row in cur.execute("""
    SELECT rowid, name, country, landmark_type, source
    FROM churches
    WHERE faith='Hindu' AND country != 'IN'
    AND name LIKE '%temple%'
    AND name NOT LIKE '%mandir%'
    AND name NOT LIKE '%kovil%' AND name NOT LIKE '%koil%'
    AND name NOT LIKE '%murugan%' AND name NOT LIKE '%ganesh%'
    AND name NOT LIKE '%shiva%' AND name NOT LIKE '%vishnu%'
    AND name NOT LIKE '%krishna%'
    ORDER BY country
    LIMIT 20
"""):
    print(f"  rowid={row[0]:>8}  {row[1][:60]:60s}  {row[2]}  lm={row[3] or '':15s}  {row[4]}")

print()

# 7. Summary of top countries with suspicious entries
print("=" * 60)
print("Top 15 countries (outside IN) with Christian-name Hindu entries")
print("=" * 60)
for r in cur.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches
    WHERE faith='Hindu' AND country != 'IN'
    AND (name LIKE '%church%' OR name LIKE '%jesus%' OR name LIKE '%christ%'
         OR name LIKE '%catholic%' OR name LIKE '%iglesia%'
         OR name LIKE '%saint%' OR name LIKE '%mission%'
         OR name LIKE '%baptist%' OR name LIKE '%lutheran%'
         OR name LIKE '%methodist%')
    GROUP BY country ORDER BY cnt DESC
    LIMIT 15
"""):
    print(f"  {r[0]:30s} {r[1]:>8,}")

conn.close()

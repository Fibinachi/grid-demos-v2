#!/usr/bin/env python3
"""
Audit Judaism (generic faith_tradition) entries for patterns
and potential misclassifications.

The 'Judaism' pool (26,156 entries) is the default for entries that
didn't match any specific tradition pattern. Let's see what's in there.
"""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
cur = conn.cursor()

total = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'").fetchone()[0]
print(f"Judaism (generic tradition) entries: {total:,}")
print()

# 1. Source breakdown
print("=" * 60)
print("Source distribution")
print("=" * 60)
for r in cur.execute("""
    SELECT source, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    GROUP BY source ORDER BY cnt DESC
"""):
    print(f"  {r[0]:35s} {r[1]:>8,}")

print()

# 2. Country breakdown
print("=" * 60)
print("Top 25 countries")
print("=" * 60)
for r in cur.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    GROUP BY country ORDER BY cnt DESC LIMIT 25
"""):
    print(f"  {r[0]:30s} {r[1]:>8,}")

print()

# 3. Christian-sounding names still in Judaism pool
print("=" * 60)
print("Christian-sounding names in Judaism pool")
print("=" * 60)
CHRISTIAN_PATTERNS = [
    ('church', '%church%'), ('jesus', '%jesus%'), ('christ', '%christ%'),
    ('catholic', '%catholic%'), ('saint', '%saint%'), ('st. ', '%st. %'),
    ('chapel', '%chapel%'), ('cathedral', '%cathedral%'), ('basilica', '%basilica%'),
    ('monastery', '%monastery%'), ('abbey', '%abbey%'), ('parish', '%parish%'),
    ('mission', '%mission%'), ('gospel', '%gospel%'), ('baptist', '%baptist%'),
    ('lutheran', '%lutheran%'), ('methodist', '%methodist%'), ('presbyterian', '%presbyterian%'),
    ('pentecostal', '%pentecostal%'), ('anglican', '%anglican%'), ('evangelical', '%evangelical%'),
    ('iglesia', '%iglesia%'), ('eglise', '%eglise%'), ('kirche', '%kirche%'),
    ('igreja', '%igreja%'), ('jesuit', '%jesuit%'), ('mennonite', '%mennonite%'),
    ('pastor', '%pastor%'), ('bishop', '%bishop%'), ('father', '%father%'),
]
total_christian = 0
for label, pat in CHRISTIAN_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {label:20s} {r:>8,}")
        total_christian += r
print(f"  {'TOTAL':20s} {total_christian:>8,}")

if total_christian > 0:
    print(f"\n  Sample entries with Christian names (up to 20):")
    for r in cur.execute("""
        SELECT rowid, name, country, landmark_type, source
        FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND (name LIKE '%church%' OR name LIKE '%jesus%' OR name LIKE '%christ%'
             OR name LIKE '%catholic%' OR name LIKE '%saint%'
             OR name LIKE '%chapel%' OR name LIKE '%cathedral%'
             OR name LIKE '%mission%' OR name LIKE '%iglesia%'
             OR name LIKE '%igreja%' OR name LIKE '%kirche%')
        LIMIT 20
    """):
        print(f"  rowid={r[0]:>8}  {str(r[1])[:65]:65s}  {r[2]}  lm={r[3] or '':15s}  {r[4]}")

print()

# 4. Muslim-sounding names
print("=" * 60)
print("Muslim-sounding names in Judaism pool")
print("=" * 60)
MUSLIM_PATTERNS = [
    ('mosque', '%mosque%'), ('masjid', '%masjid%'), ('islamic', '%islamic%'),
    ('muslim', '%muslim%'), ('allah', '%allah%'), ('muhammad', '%muhammad%'),
]
for label, pat in MUSLIM_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {label:20s} {r:>8,}")

print()

# 5. Buddhist-sounding names
print("=" * 60)
print("Buddhist-sounding names in Judaism pool")
print("=" * 60)
BUDDHIST_PATTERNS = [
    ('buddh', '%buddh%'), ('wat ', '%wat %'), ('vihara', '%vihara%'),
    ('dharma', '%dharma%'), ('sangha', '%sangha%'), ('pagoda', '%pagoda%'),
]
for label, pat in BUDDHIST_PATTERNS:
    r = cur.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if r:
        print(f"  {label:20s} {r:>8,}")

print()

# 6. Landmark_type distribution
print("=" * 60)
print("Landmark type distribution")
print("=" * 60)
for r in cur.execute("""
    SELECT COALESCE(landmark_type, 'NULL') as lm, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    GROUP BY lm ORDER BY cnt DESC
"""):
    print(f"  {r[0]:20s} {r[1]:>8,}")

print()

# 7. Denominations in Judaism pool
print("=" * 60)
print("Top denominations in Judaism pool")
print("=" * 60)
for r in cur.execute("""
    SELECT COALESCE(denomination, 'NULL') as denom, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    GROUP BY denom ORDER BY cnt DESC LIMIT 20
"""):
    print(f"  {str(r[0])[:40]:40s} {r[1]:>8,}")

print()

# 8. Key diaspora countries — check specific country patterns
print("=" * 60)
print("Israel (IL) entries — synagogue/synagog vs other patterns")
print("=" * 60)
il_total = cur.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Jewish' AND faith_tradition='Judaism' AND country='IL'
""").fetchone()[0]
print(f"  Total IL entries: {il_total:,}")

il_synagogue = cur.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Jewish' AND faith_tradition='Judaism' AND country='IL'
    AND (name LIKE '%synagog%' OR name LIKE '%beit knesset%' OR name LIKE '%בית כנסת%'
         OR name LIKE '%shul%' OR name LIKE '%temple%')
""").fetchone()[0]
print(f"  Synagogue/synagog in name: {il_synagogue:,}")

# Check for non-synagogue-named entries in IL
print(f"  Non-synagogue named (sample):")
for r in cur.execute("""
    SELECT rowid, name, landmark_type, source
    FROM churches
    WHERE faith='Jewish' AND faith_tradition='Judaism' AND country='IL'
    AND name NOT LIKE '%synagog%' AND name NOT LIKE '%beit knesset%'
    AND name NOT LIKE '%בית כנסת%' AND name NOT LIKE '%shul%'
    AND name NOT LIKE '%temple%'
    LIMIT 15
"""):
    print(f"    rowid={r[0]:>8}  {str(r[1])[:65]:65s}  lm={r[2] or '':15s}  {r[3]}")

conn.close()

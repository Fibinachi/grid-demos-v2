#!/usr/bin/env python3
"""
Phase C: Reclassify clearly non-Jewish entries still in the Judaism pool.

Targets entries where landmark_type or denomination contradicts faith=Jewish.
Conservative approach — requires multiple signals to reclassify.
"""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
cur = conn.cursor()
cur.execute("PRAGMA busy_timeout=30000")

def run(label, sql):
    n = cur.execute(sql).rowcount
    if n:
        print(f"  {label}: {n:,}")
    conn.commit()
    return n

def where_j():
    return "faith='Jewish' AND faith_tradition='Judaism'"

print("=" * 60)
print("Phase C: Fix Jewish misclassifications by landmark/denom")
print("=" * 60)

# ═══════════════════════════════════════════════════════════
# C1: landmark_type clearly Christian + denomination mismatch
# ═══════════════════════════════════════════════════════════
print("\n--- C1: landmark_type=church/cathedral/basilica → Christian ---")
# Landmark is a church AND denomination is Christian → slam dunk
CHRISTIAN_DENOMS = [
    'Baptist', 'Lutheran', 'Methodist', 'Presbyterian', 'Pentecostal',
    'Anglican', 'Episcopal', 'Reformed', 'Mennonite', 'Anabaptist',
    'Churches of Christ', 'Church of Christ', 'Church of God',
    'Church of the Nazarene', 'Adventist', 'Seventh-day Adventist',
    'Evangelical', 'Foursquare', 'Wesleyan', 'Vineyard',
    'Assemblies of God', 'Christian Reformed', 'Moravian',
    'Salvation Army', 'Quaker', 'Unitarian Universalist',
]
for d in CHRISTIAN_DENOMS:
    run(f"  denom contains '{d}' + lm=church/cathedral", f"""
        UPDATE churches SET faith='Christian', faith_tradition='Christian'
        WHERE {where_j()}
        AND denomination LIKE '%{d.replace("'", "''")}%'
        AND landmark_type IN ('church', 'cathedral', 'basilica', 'chapel')
    """)

# Also catch specific denominations that map to specific traditions
DENOM_TRADITION_MAP = {
    'Eastern Orthodox': 'Orthodox (Eastern)',
    'Oriental Orthodox': 'Orthodox (Oriental)',
    'Coptic': 'Orthodox (Oriental)',
    'Roman Catholic': 'Catholic',
    'Catholic': 'Catholic',
    'AME': 'Methodist',
    'African Methodist': 'Methodist',
    'AME Zion': 'Methodist',
    'Christian Methodist': 'Methodist',
}
for denom, trad in DENOM_TRADITION_MAP.items():
    run(f"  denom={denom} → {trad}", f"""
        UPDATE churches SET faith='Christian', faith_tradition='{trad}'
        WHERE {where_j()}
        AND denomination LIKE '%{denom.replace("'", "''")}%'
    """)

# ═══════════════════════════════════════════════════════════
# C2: landmark_type clearly Christian — name pattern backup
# ═══════════════════════════════════════════════════════════
print("\n--- C2: lm=church + Christian name keywords → Christian ---")
# Even without denomination, church landmark + Christian name = safe
run("lm=church + 'church' in name", f"""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE {where_j()}
    AND landmark_type = 'church'
    AND (name LIKE '%church%' OR name LIKE '%iglesia%' OR name LIKE '%igreja%'
         OR name LIKE '%eglise%' OR name LIKE '%kirche%' OR name LIKE '%kirk%'
         OR name LIKE '%chiesa%' OR name LIKE '%església%')
    AND name NOT LIKE '%synagogue%' AND name NOT LIKE '%shul%'
    AND name NOT LIKE '%chabad%' AND name NOT LIKE '%hasidic%'
    AND name NOT LIKE '%israel%' AND name NOT LIKE '%hebrew%'
    AND name NOT LIKE '%talmud%' AND name NOT LIKE '%yeshiva%'
    AND name NOT LIKE '%jewish%' AND name NOT LIKE '%judaism%'
    AND name NOT LIKE '%rabbi%' AND name NOT LIKE '%knesset%'
""")

run("lm=church + saint/jesus/christ/catholic in name", f"""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE {where_j()}
    AND landmark_type = 'church'
    AND (name LIKE '%saint%' OR name LIKE '%st. %' OR name LIKE '%san%'
         OR name LIKE '%santo%' OR name LIKE '%santa%'
         OR name LIKE '%jesus%' OR name LIKE '%christ%'
         OR name LIKE '%catholic%' OR name LIKE '%católica%'
         OR name LIKE '%cristo%' OR name LIKE '%cristian%'
         OR name LIKE '%baptist%' OR name LIKE '%bautista%'
         OR name LIKE '%lutheran%' OR name LIKE '%luterana%'
         OR name LIKE '%methodist%' OR name LIKE '%metodista%'
         OR name LIKE '%presbyterian%' OR name LIKE '%presbiteriana%'
         OR name LIKE '%pentecostal%' OR name LIKE '%evangelical%'
         OR name LIKE '%evangélico%' OR name LIKE '%gospel%'
         OR name LIKE '%mission%' OR name LIKE '%parish%'
         OR name LIKE '%monastery%' OR name LIKE '%abbey%'
         OR name LIKE '%chapel%' OR name LIKE '%cathedral%'
         OR name LIKE '%bishop%' OR name LIKE '%father%'
         OR name LIKE '%pastor%' OR name LIKE '%jesuit%')
    AND name NOT LIKE '%synagogue%' AND name NOT LIKE '%shul%'
    AND name NOT LIKE '%chabad%' AND name NOT LIKE '%hasidic%'
    AND name NOT LIKE '%israel%' AND name NOT LIKE '%hebrew%'
    AND name NOT LIKE '%rabbi%'
""")

# ═══════════════════════════════════════════════════════════
# C3: Mosque landmark → Islam
# ═══════════════════════════════════════════════════════════
print("\n--- C3: landmark_type=mosque → Islam ---")
run("lm=mosque", f"""
    UPDATE churches SET faith='Islam', faith_tradition='Muslim'
    WHERE {where_j()}
    AND landmark_type = 'mosque'
""")

# ═══════════════════════════════════════════════════════════
# C4: lm=church with no Christian keywords — check specific patterns
# ═══════════════════════════════════════════════════════════
print("\n--- C4: lm=church + Buddhist/Eastern keywords → Buddhist ---")
run("lm=church + buddhist keywords", f"""
    UPDATE churches SET faith='Buddhist', faith_tradition='Buddhist'
    WHERE {where_j()}
    AND landmark_type = 'church'
    AND (name LIKE '%buddh%' OR name LIKE '%wat %' OR name LIKE '%vihara%'
         OR name LIKE '%dharma%' OR name LIKE '%sangha%'
         OR name LIKE '%pagoda%' OR name LIKE '%monk%')
""")

# ═══════════════════════════════════════════════════════════
# C5: landmark_type NULL + Christian denomination → Christian
# ═══════════════════════════════════════════════════════════
print("\n--- C5: NULL landmark + Christian denomination → Christian ---")
for d in CHRISTIAN_DENOMS:
    run(f"  NULL lm + denom {d}", f"""
        UPDATE churches SET faith='Christian', faith_tradition='Christian'
        WHERE {where_j()}
        AND denomination LIKE '%{d.replace("'", "''")}%'
        AND (landmark_type IS NULL OR landmark_type = '')
    """)
for denom, trad in DENOM_TRADITION_MAP.items():
    run(f"  NULL lm + denom {denom} → {trad}", f"""
        UPDATE churches SET faith='Christian', faith_tradition='{trad}'
        WHERE {where_j()}
        AND denomination LIKE '%{denom.replace("'", "''")}%'
        AND (landmark_type IS NULL OR landmark_type = '')
    """)

# ═══════════════════════════════════════════════════════════
# C6: landmark_type=synagogue BUT name is Christian-sounding AND no Jewish keywords
# These may be legitimate Christian orgs tagged as synagogue by the pipeline
# Only fix if there are MULTIPLE Christian signals and NO Jewish signals
# ═══════════════════════════════════════════════════════════
print("\n--- C6: lm=synagogue + Christian name + Christian denom → Christian ---")
# "CHRISTIAN CONGREGATION IN THE UNITED STATES" pattern
run("'Christian Congregation' in name + lm=synagogue", f"""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE {where_j()}
    AND landmark_type = 'synagogue'
    AND name LIKE '%christian congregation%'
""")

# Other Christian-named synagogues that are clearly churches
# These have both Christian keywords AND Christian denominations
run("lm=synagogue + Christian name + Christian denom", f"""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE {where_j()}
    AND landmark_type = 'synagogue'
    AND (name LIKE '%church%' OR name LIKE '%iglesia%' OR name LIKE '%igreja%')
    AND name NOT LIKE '%israel%' AND name NOT LIKE '%hebrew%'
    AND name NOT LIKE '%jewish%' AND name NOT LIKE '%rabbi%'
    AND name NOT LIKE '%shalom%' AND name NOT LIKE '%beth %'
    AND name NOT LIKE '%temple%' AND name NOT LIKE '%zion%'
    AND denomination IN (
        'Assemblies of God', 'Baptist', 'Lutheran', 'Methodist',
        'Presbyterian', 'Pentecostal', 'Anglican', 'Christian',
        'Church of God', 'Church of the Nazarene', 'Episcopal',
        'Evangelical', 'Foursquare', 'Mennonite', 'Non-Denominational',
        'Reformed', 'Roman Catholic', 'Catholic', 'Vineyard',
        'Wesleyan', 'AME', 'African Methodist Episcopal Church',
        'Christian Science (First Church of Christ, Scientist)',
        'Churches of Christ', 'Church of Christ',
        'Seventh-day Adventist', 'Interdenominational',
        'Unitarian Universalist', 'Quaker',
        'Eastern Orthodox', 'Oriental Orthodox (Coptic)',
        'Moravian Church in North America',
        'Community Church (unspecified)',
        'United Church of Christ', 'United Methodist Church',
        'Wisconsin Evangelical Lutheran Synod',
        'International Pentecostal Holiness Churc',
        'Church of God in Christ', 'Church of God (Cleveland, TN)',
        'Lutheran Church - Missouri Synod',
        'Evangelical Lutheran Church in America',
        'Presbyterian Church in America',
        'Presbyterian Church (U.S.A.)'
    )
""")


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

jewish_now = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
judaism_now = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'").fetchone()[0]
print(f"Jewish total: {jewish_now:,}")
print(f"  Judaism (generic): {judaism_now:,}")

print(f"\nTop 10 remaining landmark types in Judaism pool:")
for r in cur.execute("""
    SELECT COALESCE(landmark_type, 'NULL') as lm, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    GROUP BY lm ORDER BY cnt DESC LIMIT 10
"""):
    print(f"  {r[0]:20s} {r[1]:>8,}")

print(f"\nAny Christian denominations still in Judaism pool?")
remaining = cur.execute("""
    SELECT denomination, COUNT(*) as cnt
    FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism'
    AND denomination IS NOT NULL AND denomination != ''
    AND denomination NOT IN ('Jewish', 'Jewish (unclassified)')
    AND denomination NOT LIKE 'Jewish%'
    GROUP BY denomination ORDER BY cnt DESC LIMIT 20
""").fetchall()
if remaining:
    for r in remaining:
        print(f"  {str(r[0])[:45]:45s} {r[1]:>8}")
else:
    print("  None!")

print(f"\nAny remaining Christian-sounding names?")
remaining_christian = 0
for label, pat in [
    ('church name', '%church%'), ('iglesia', '%iglesia%'),
    ('christ', '%christ%'), ('jesus', '%jesus%'),
    ('catholic', '%catholic%'), ('saint', '%saint%'),
]:
    n = cur.execute(f"""
        SELECT COUNT(*) FROM churches
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND name LIKE ?
    """, (pat,)).fetchone()[0]
    if n:
        print(f"  {label:15s} {n:>8}")
        remaining_christian += n
if remaining_christian == 0:
    print("  None!")

conn.close()

#!/usr/bin/env python3
"""
_classify_jewish.py — Jewish tradition classifier and Christian misclassification fixer.

Two phases:
  Phase A: Reclassify Christian/Muslim entries that somehow got faith=Jewish.
  Phase B: Classify faith_tradition for remaining Jewish entries by name/denom patterns.

Tiers:
  1. Reclassify Christian (faith_tradition or denomination is clearly Christian)
  2. Reclassify Muslim (faith_tradition=Muslim)  
  3. Name-based Jewish tradition classification
  4. Denomination-based Jewish tradition classification
  5. Default: fill with faith_tradition='Jewish' where NULL
"""
import sqlite3, re, time

DB = "churches.db"

conn = sqlite3.connect(DB, timeout=60)
# Register REGEXP function — SQLite doesn't have it built-in
def regexp(expr, item):
    if item is None:
        return 0
    try:
        return 1 if re.search(expr, str(item), re.IGNORECASE) else 0
    except re.error:
        return 0
conn.create_function("REGEXP", 2, regexp)

c = conn.cursor()
c.execute("PRAGMA busy_timeout=30000")

def log(label, count):
    if count and count > 0:
        print(f"  {label}: {count:,}")

def count_jewish():
    return c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]

def count_trad(trad):
    return c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition=?", (trad,)).fetchone()[0]

# ═══════════════════════════════════════════════════════════════
# PHASE A: Reclassify Christian/Muslim misclassifications
# ═══════════════════════════════════════════════════════════════

print("=" * 60)
print("PHASE A: Reclassify Christian & Muslim misclassifications")
print("=" * 60)
print(f"Jewish entries before: {count_jewish():,}")

# ── A1: Christian faith_tradition entries ────────────────────
print("\n--- A1: faith_tradition is Christian denomination ---")
CHRISTIAN_TRADS = (
    'Christian', 'Baptist', 'Lutheran', 'Catholic', 'Pentecostal',
    'Methodist', 'Anglican', 'Presbyterian', 'Churches of Christ',
    'Anabaptist', 'Independent catholic', 'Unitarian Universalist',
    'Mennonite', 'Reformed', 'Foursquare', 'Vineyard', 'Wesleyan',
    'Evangelical', 'Episcopalian', 'Church of God', 'Adventist',
    'Disciples of Christ', 'Moravian', 'Brethren', 'Congregational',
    'Salvation Army', 'Church of the Nazarene', 'Christian Reformed',
    'Christian Science', 'Quaker', 'Latter-day Saints', 'Mormon',
    'Jehovah\'s Witnesses', 'Orthodox (Eastern)',
)

for trad in CHRISTIAN_TRADS:
    c.execute("""
        UPDATE churches SET faith='Christian', faith_tradition=?
        WHERE faith='Jewish' AND faith_tradition=?
    """, (trad, trad))
    log(trad, c.rowcount)
conn.commit()

# ── A2: Christian denominations in denomination field ────────
print("\n--- A2: Christian denomination (non-AME handled above via trad) ---")
# AME entries with faith_tradition='Judaism' need special handling
# AME is a Christian denomination but faith_tradition='Judaism'
ame_count = c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Jewish' AND faith_tradition='Judaism'
    AND denomination IN (
        'AME', 'African Methodist Episcopal Church',
        'African Methodist Episcopal Zion Church', 'AME Zion',
        'Christian Methodist Episcopal Church'
    )
""").rowcount
log("AME (Judaism trad→Christian)", ame_count)
conn.commit()

# ── A3: Assemblies of God / other Pentecostal with Judaism trad ─
for denom in ('Assemblies of God', 'Latter Rain Pentecostal'):
    c.execute("""
        UPDATE churches SET faith='Christian', faith_tradition='Pentecostal'
        WHERE faith='Jewish' AND faith_tradition='Judaism'
        AND denomination=?
    """, (denom,))
    log(f"Pentecostal ({denom})", c.rowcount)
conn.commit()

# ── A4: Mennonite (Judaism trad) ──
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Mennonite'
    WHERE faith='Jewish' AND faith_tradition='Judaism'
    AND (denomination LIKE '%Mennonite%' OR denomination LIKE '%Amish%')
""")
log("Mennonite (Judaism trad→Christian)", c.rowcount)
conn.commit()

# ── A5: Christian faith_tradition with 'Judaism' trad ──
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Jewish' AND faith_tradition='Judaism'
    AND denomination IN (
        'Non-Denominational', 'Non-Denominational / Independent',
        'Christian', 'Vineyard', 'Foursquare Church',
        'Unitarian Universalist', 'Christian Science (First Church of Christ, Scientist)',
        'Churches of Christ', 'Church of the Nazarene',
        'Presbyterian Church in America', 'Presbyterian Church (U.S.A.)',
        'United Methodist Church', 'Methodist',
        'Evangelical Lutheran Church in America', 'Lutheran Church - Missouri Synod',
        'Reformed Church in America', 'Christian Reformed Church in North America',
        'Southern Baptist Convention', 'Baptist',
        'Religious Society of Friends (Quakers)', 'Quaker',
        'Roman Catholic', 'Catholic',
        'Episcopal Church', 'Anglican',
        'Church of God', 'Church of God of Prophecy',
        'Seventh-day Adventist', 'Advent Christian'
    )
""")
log("Christian-denom+Judaism→Christian", c.rowcount)
conn.commit()

# ── A6: Non-religious → set correctly ──
c.execute("""
    UPDATE churches SET faith='Non-religious', faith_tradition='Secular'
    WHERE faith='Jewish' AND faith_tradition='Non_religious'
""")
log("Non_religious→Non-religious", c.rowcount)
conn.commit()

# ── A7: Muslim faith_tradition → Islam ──
c.execute("""
    UPDATE churches SET faith='Islam', faith_tradition='Muslim'
    WHERE faith='Jewish' AND faith_tradition='Muslim'
""")
log("Muslim (faith_tradition=Muslim→Islam)", c.rowcount)

# Also handle faith_tradition='Judaism' with Muslim-sounding names or denomination
c.execute("""
    UPDATE churches SET faith='Islam', faith_tradition='Muslim'
    WHERE faith='Jewish' AND faith_tradition='Judaism'
    AND (name LIKE '%mosque%' OR name LIKE '%masjid%' OR name LIKE '%islamic%'
         OR name LIKE '%muslim%' OR name LIKE '%jami%')
""")
log("Muslim (name patterns)", c.rowcount)
conn.commit()

# ── A8: Sikh/Buddhist/Bahai etc with Judaism trad ──
c.execute("""
    UPDATE churches SET faith='Sikh', faith_tradition='Sikh'
    WHERE faith='Jewish' AND faith_tradition='Sikh'
""")
log("Sikh→Sikh", c.rowcount)

c.execute("""
    UPDATE churches SET faith='Buddhist', faith_tradition='Buddhist'
    WHERE faith='Jewish' AND faith_tradition='Buddhist'
""")
log("Buddhist→Buddhist", c.rowcount)
conn.commit()

print(f"\nJewish entries after Phase A: {count_jewish():,}")


# ═══════════════════════════════════════════════════════════════
# PHASE B: Classify Jewish traditions
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("PHASE B: Classify Jewish traditions by name/denom patterns")
print("=" * 60)

# ── B1: Chabad ───────────────────────────────────────────────
print("\n--- B1: Chabad-Lubavitch → Orthodox (Chabad) ---")
# By name
c.execute("""
    UPDATE churches SET faith_tradition='Orthodox (Chabad)'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND name LIKE '%chabad%'
""")
log("name Chabad", c.rowcount)

# By denomination
c.execute("""
    UPDATE churches SET faith_tradition='Orthodox (Chabad)', denomination='Jewish (Chabad)'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND denomination='Jewish (Chabad)'
""")
log("denom Jewish (Chabad)", c.rowcount)

c.execute("""
    UPDATE churches SET faith_tradition='Orthodox (Chabad)'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%lubavitch%' OR name LIKE '%lubavich%')
""")
log("name Lubavitch", c.rowcount)
conn.commit()

# ── B2: Hasidic groups ──────────────────────────────────────
print("\n--- B2: Hasidic → Orthodox (Hasidic) ---")
HASIDIC_PATTERNS = [
    (r'\bsatmar\b', 'Satmar'),
    (r'\bbelz\b', 'Belz'),
    (r'\bgur\b', 'Gur'),
    (r'\bbobov\b', 'Bobov'),
    (r'\bbreslov\b', 'Breslov'),
    (r'\bvizhnitz\b', 'Vizhnitz'),
    (r'\bmunkacs\b', 'Munkacs'),
    (r'\bstolin\b', 'Stolin'),
    (r'\bskver\b', 'Skver'),
    (r'\bmonsey\b', 'Monsey/Hasidic'),
    (r'\bwilliamsburg\s*(hasidic|jewish|synagogue)\b', 'Williamsburg/Hasidic'),
    (r'\bchasid\b', 'Hasidic'),
    (r'\bhasid\b', 'Hasidic'),
    (r'\bk[`\']?hal\s+chasidim\b', 'Hasidic'),
    (r'\bohel\s+(moishe|moshe)\b', 'Hasidic'),
    (r'\byetev\s+lev\b', 'Satmar'),
]

for pat, group in HASIDIC_PATTERNS:
    c.execute("""
        UPDATE churches SET faith_tradition='Orthodox (Hasidic)'
        WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
        AND name REGEXP ?
    """, (pat,))
    log(f"Hasidic ({group})", c.rowcount)
conn.commit()

# ── B3: Yeshiva/Kollel/Mesivta → Orthodox ──────────────────
print("\n--- B3: Yeshiva/Kollel/Mesivta → Orthodox ---")
ORTHODOX_PATTERNS = [
    (r'\byeshiva\b', 'Yeshiva'),
    (r'\byeshivah\b', 'Yeshiva'),
    (r'\bkollel\b', 'Kollel'),
    (r'\bmesivta\b', 'Mesivta'),
    (r'\bbeis medrash\b', 'Beis Medrash'),
    (r'\bbeth midrash\b', 'Beth Midrash'),
    (r'\btalmud\b', 'Talmud'),
    (r'\b(institute|seminary)\s+.*\btorah\b', 'Torah Institute'),
    (r'\btorah\s+(institute|seminary|center|academy|college)\b', 'Torah Institute'),
]
for pat, group in ORTHODOX_PATTERNS:
    c.execute("""
        UPDATE churches SET faith_tradition='Orthodox'
        WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
        AND name REGEXP ?
    """, (pat,))
    log(f"Orthodox ({group})", c.rowcount)

# Young Israel = Orthodox
c.execute("""
    UPDATE churches SET faith_tradition='Orthodox'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%young israel%' OR name LIKE '%Young Israel%')
""")
log("Young Israel", c.rowcount)

# Union of Orthodox / National Jewish / OU
c.execute("""
    UPDATE churches SET faith_tradition='Orthodox'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%union of orthodox%' OR name LIKE '%orthodox union%'
         OR name LIKE '%national jewish%')
""")
log("OU/National", c.rowcount)
conn.commit()

# ── B4: Sephardi/Mizrahi ────────────────────────────────────
print("\n--- B4: Sephardi/Mizrahi → Sephardic ---")
SEPHARDI_PATTERNS = [
    (r'\bsephard\w*\b', 'Sephardi keyword'),
    (r'\bmizrah\w*\b', 'Mizrahi keyword'),
    (r'\bspanish\s+(and\s+)?portuguese\b', 'Spanish-Portuguese'),
    (r'\bportuguese\s+(synagogue|jewish|israelite)\b', 'Portuguese Jewish'),
    (r'\bmarrano\b', 'Marrano'),
    (r'\bconverso\b', 'Converso'),
    (r'\baleppo\b', 'Aleppan'),
    (r'\bbaghdadi\b', 'Baghdadi'),
    (r'\bbucharian\b', 'Bucharian'),
    (r'\byemenite\b', 'Yemenite'),
    (r'\bbeta\s+israel\b', 'Beta Israel'),
    (r'\bethiopian\s+jewish\b', 'Ethiopian Jewish'),
    (r'\bor mizrah\b', 'Or Mizrah'),
    (r'\brambam\b', 'Rambam'),
]
for pat, group in SEPHARDI_PATTERNS:
    c.execute("""
        UPDATE churches SET faith_tradition='Sephardic'
        WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
        AND name REGEXP ?
    """, (pat,))
    log(f"Sephardic ({group})", c.rowcount)
conn.commit()

# ── B5: Reform ──────────────────────────────────────────────
print("\n--- B5: Reform ---")
c.execute("""
    UPDATE churches SET faith_tradition='Reform'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%reform%' OR name LIKE '%temple%')
    AND country='US'
    AND source IN ('holy_sites_import', 'osm_import')
    AND name NOT LIKE '%chabad%'
    AND name NOT LIKE '%lubavitch%'
    AND name NOT LIKE '%orthodox%'
""")
log("US Temple/Reform (holy_sites+osm)", c.rowcount)
conn.commit()

# More precise Reform patterns
REFORM_PATTERNS = [
    (r'\breform\b', 'Reform keyword'),
    (r'\bliberal\s+jewish\b', 'Liberal Judaism'),
    (r'\bprogressive\s+jewish\b', 'Progressive Judaism'),
    (r'\btemple\s+(beth|bet|b[`\']?nai|shalom|emanuel|emmanuel|israel|sinai|judea|zion|sholom|aharoh|am|avodah|chai|dorah|eliyah|haverim|kol|menorah|shir|tikvah|yisrael)\b', 'Temple (Reform/Conserv)'),
    (r'\bcongregation\s+(beth|bet|b[`\']?nai|shalom|emanuel|emmanuel|israel|sinai)\b', 'Congregation (likely Reform/Conserv)'),
]
for pat, group in REFORM_PATTERNS:
    c.execute("""
        UPDATE churches SET faith_tradition='Reform'
        WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
        AND name REGEXP ?
        AND name NOT LIKE '%orthodox%'
        AND name NOT LIKE '%chabad%'
        AND name NOT LIKE '%sephard%'
    """, (pat,))
    log(f"Reform ({group})", c.rowcount)
conn.commit()

# ── B6: Conservative ────────────────────────────────────────
print("\n--- B6: Conservative ---")
CONSERVATIVE_PATTERNS = [
    (r'\bconservative\b', 'Conservative keyword'),
    (r'\bmasorti\b', 'Masorti'),
    (r'\buscj\b', 'USCJ'),
    (r'\bunited\s+synagogue\b', 'United Synagogue'),
]
for pat, group in CONSERVATIVE_PATTERNS:
    c.execute("""
        UPDATE churches SET faith_tradition='Conservative'
        WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
        AND name REGEXP ?
    """, (pat,))
    log(f"Conservative ({group})", c.rowcount)
conn.commit()

# ── B7: Reconstructionist ───────────────────────────────────
print("\n--- B7: Reconstructionist ---")
c.execute("""
    UPDATE churches SET faith_tradition='Reconstructionist'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%reconstructionist%' OR name LIKE '%jrf%')
""")
log("Reconstructionist", c.rowcount)
conn.commit()

# ── B8: Other traditions ────────────────────────────────────
print("\n--- B8: Other Jewish traditions ---")
c.execute("""
    UPDATE churches SET faith_tradition='Humanistic'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%humanistic%' OR name LIKE '%humanist%')
""")
log("Humanistic", c.rowcount)

c.execute("""
    UPDATE churches SET faith_tradition='Karaite'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%karaite%' OR name LIKE '%karaim%' OR name LIKE '%caraim%')
""")
log("Karaite", c.rowcount)

c.execute("""
    UPDATE churches SET faith_tradition='Messianic'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND (name LIKE '%messianic%' OR name LIKE '%messian%' OR name LIKE '%yahshua%'
         OR name LIKE '%yeshua%')
""")
log("Messianic", c.rowcount)
conn.commit()

# ── B9: 'Temple' in US (non-orthodox/non-chabad remaining) ──
print("\n--- B9: Temple (remaining US) → Reform ---")
c.execute("""
    UPDATE churches SET faith_tradition='Reform'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND country='US'
    AND name LIKE '%temple%'
    AND name NOT LIKE '%chabad%'
    AND name NOT LIKE '%lubavitch%'
""")
log("US Temple (remaining)", c.rowcount)
conn.commit()

# ── B10: By denomination field ──────────────────────────────
print("\n--- B10: Denomination-based classification ---")
c.execute("""
    UPDATE churches SET faith_tradition='Orthodox'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))
    AND denomination='Jewish'
""")
log("denom=Jewish → Orthodox (default)", c.rowcount)
conn.commit()

# ── B11: Default remaining → 'Judaism' ─────────────────────
print("\n--- B11: Remaining → faith_tradition='Judaism' ---")
c.execute("""
    UPDATE churches SET faith_tradition='Judaism'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition='')
""")
log("Default to Judaism", c.rowcount)
conn.commit()


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

final_jewish = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
print(f"Jewish entries: {final_jewish:,}")

# Also check Christian entries we reclassified
reclassified = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND sqlite_version() > '0'").fetchone()
# Actually let's check the correct way:
christian_before = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Christian' 
    AND (faith_tradition IN ('Christian','Baptist','Lutheran','Catholic','Pentecostal',
                             'Methodist','Anglican','Presbyterian','Churches of Christ',
                             'Anabaptist','Mennonite','Foursquare','Vineyard') 
         OR denomination IN ('Assemblies of God','Jewish (Chabad)'))
""").fetchone()

# Just count Christian
christian_total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian'").fetchone()[0]
print(f"Christian (total): {christian_total:,}")

print(f"\nJewish faith_tradition distribution:")
for r in c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {str(r[0] or 'NULL'):30s} {r[1]:>8}")

print(f"\nJewish denomination distribution:")
for r in c.execute("SELECT denomination, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15"):
    print(f"  {str(r[0] or 'NULL'):40s} {r[1]:>8}")

print(f"\nJewish by country (top 15):")
for r in c.execute("SELECT country, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15"):
    print(f"  {r[0]:30s} {r[1]:>8}")

conn.close()

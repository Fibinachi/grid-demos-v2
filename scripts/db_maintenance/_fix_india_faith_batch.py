"""
Complete batch-based fix for ALL India faith tag misclassifications.
Uses SQL LIKE conditions for speed.
"""
import sqlite3
import datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

total_fixes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Fix Jewish → Hindu (Hindu temples wrongly tagged as Jewish)
# ═══════════════════════════════════════════════════════════════════════════════
# These are clearly Hindu temples - keep ONLY synagogues as Jewish
synagogue_keepers = [
    "%synagogue%", "%synagog%", "%chabad%", "%jewish%",
    "%magen%", "%keneseth%", "%paradesi%", "%succath%",
    "%judah%", "%beyth%", "%beit%", "%beth el%",
    "%tiphaereth%", "%shiloh fellowship%", "%gate of mercy%",
    "%mala jewish%", "%ohel david%", "%beith shalom%",
]

print("=== 1. Fixing Jewish → Hindu ===")
# Build exclusion for synagogues
exclude = " AND ".join([f"LOWER(name) NOT LIKE '{k}'" for k in synagogue_keepers])
c.execute(f"""
    UPDATE churches SET faith='Hindu', faith_tradition='Hinduism'
    WHERE country='IN' AND faith='Jewish' AND source='holy_sites_import'
      AND ({exclude})
""")
print(f"  Fixed Jewish→Hindu: {c.rowcount}")
total_fixes += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Fix Hindu → Christian (churches wrongly tagged as Hindu)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 2. Fixing Hindu → Christian ===")
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity'
    WHERE country='IN' AND faith='Hindu' AND source='holy_sites_import'
      AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%cathedral%'
           OR LOWER(name) LIKE '%basilica%' OR LOWER(name) LIKE '%masihi mandir%')
      AND LOWER(name) NOT LIKE '%temple church%'
""")
print(f"  Fixed Hindu→Christian: {c.rowcount}")
total_fixes += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Fix Hindu → Sikh (gurudwaras wrongly tagged as Hindu)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 3. Fixing Hindu → Sikh ===")
c.execute("""
    UPDATE churches SET faith='Sikh', faith_tradition='Sikhism'
    WHERE country='IN' AND faith='Hindu' AND source='holy_sites_import'
      AND (LOWER(name) LIKE '%gurudwara%' OR LOWER(name) LIKE '%gurdwara%')
""")
print(f"  Fixed Hindu→Sikh: {c.rowcount}")
total_fixes += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Fix Hindu → Islam (mosques/masjids wrongly tagged as Hindu)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 4. Fixing Hindu → Islam ===")
c.execute("""
    UPDATE churches SET faith='Islam', faith_tradition='Islam'
    WHERE country='IN' AND faith='Hindu' AND source='holy_sites_import'
      AND (LOWER(name) LIKE '%masjid%' OR LOWER(name) LIKE '%mosque%'
           OR LOWER(name) LIKE '%muslim%')
""")
print(f"  Fixed Hindu→Islam: {c.rowcount}")
total_fixes += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Fix Christian → Hindu (temples/mandirs wrongy tagged as Christian)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 5. Fixing Christian → Hindu ===")

hindu_patterns = [
    "% temple%", "% mandir%", "%kovil%", "% mandapam%", "%haveli%",
    "%swamy%", "%swami%", "%ganpati%", "%ganesh%", "%shiva%", "%vishnu%",
    "%durga%", "%kali%", "%krishna%", "%hanuman%", "%lakshmi%",
    "%saraswati%", "%ayyappa%", "%ayyapa%", "%devi%", "%mataji%",
    "%shakti%", "%sai baba%", "%jain%", "%matha%", "%math %",
    "%baba %", "%dham%", "%dhaam%", "%peeth%", "%ashram%", "%gaddi%",
    "%shankar%", "%mahadev%", "%lingam%", "%linga%", "%nath%", "%pir%",
    "%dargah%", "%samadhi%", "%sansthan%", "%mutt%", "%guruji%", "%sadhu%",
    "%murugan%", "%perumal%", "%siddhar%", "%koil%", "%koyil%", "%thirukoyil%",
]

christian_exclude = [
    "%church%", "%cathedral%", "%basilica%", "%chapel%",
    "%orthodox%", "%catholic%", "%protestant%", "%presbyterian%",
    "%baptist%", "%methodist%", "%lutheran%", "%pentecostal%",
    "%evangelical%", "%adventist%", "%assembly of god%",
    "%salvation army%", "%jesuit%", "%franciscan%", "%dominican%",
    "%st. %", "%saint%", "%notre dame%", "%our lady%",
    "%good shepherd%", "%redeemer%", "%saviour%", "%savior%",
    "%christ the%", "%jesus%", "%christian%", "%messiah%",
    "%immaculate%", "%rosary%", "%cristo%", "%cristu%", "%yeshu%",
    "%mar thoma%", "%csi %", "%cn i%", "%malankara%", "%jacobite%",
    "%syrian%", "%syro-malabar%", "%syro-malankara%",
    "%mission%", "%diocese%", "%parish%", "%pastoral%",
    "%ecumenical%", "%fellowship%", "%worship%", "%ministry%",
    "%bible%", "%gospel%", "%grace%", "%faith%",
    "%cross%", "%calvary%", "%bethlehem%", "%nazareth%",
    "%hope church%", "%prayer%", "%healing%",
]

for hpattern in hindu_patterns:
    where_parts = [
        "country='IN'",
        "faith='Christian'",
        "source='holy_sites_import'",
        f"LOWER(name) LIKE '{hpattern}'"
    ]
    for cex in christian_exclude:
        where_parts.append(f"LOWER(name) NOT LIKE '{cex}'")
    
    where_clause = " AND ".join(where_parts)
    c.execute(f"UPDATE churches SET faith='Hindu', faith_tradition='Hinduism' WHERE {where_clause}")
    if c.rowcount > 0:
        total_fixes += c.rowcount

conn.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE country='IN' AND faith='Hindu'")
total_hindu = c.fetchone()[0]
print(f"  Total Christian→Hindu fixes applied (cumulative)")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Edge cases
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 6. Edge cases ===")

# Muslim Temple → Hindu
c.execute("""
    UPDATE churches SET faith='Hindu', faith_tradition='Hinduism'
    WHERE country='IN' AND faith='Islam' AND source='holy_sites_import'
      AND LOWER(name) LIKE '%temple%'
      AND LOWER(name) NOT LIKE '%mosque%' AND LOWER(name) NOT LIKE '%masjid%'
""")
if c.rowcount > 0:
    print(f"  Fixed Islam→Hindu: {c.rowcount}")
    total_fixes += c.rowcount

# Ohel David → Jewish (famous Pune synagogue)
c.execute("""
    UPDATE churches SET faith='Jewish', faith_tradition='Judaism'
    WHERE country='IN' AND LOWER(name) LIKE '%ohel david%' AND faith != 'Jewish'
""")
if c.rowcount > 0:
    print(f"  Fixed →Jewish (Ohel David): {c.rowcount}")
    total_fixes += c.rowcount

# Beith Shalom → Jewish
c.execute("""
    UPDATE churches SET faith='Jewish', faith_tradition='Judaism'
    WHERE country='IN' AND LOWER(name) LIKE '%beith shalom%' AND faith != 'Jewish'
""")
if c.rowcount > 0:
    print(f"  Fixed →Jewish (Beith Shalom): {c.rowcount}")
    total_fixes += c.rowcount

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Log
# ═══════════════════════════════════════════════════════════════════════════════
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_fix_india_faith_batch.py', TS, TS,
      total_fixes, 0, 'faith,faith_tradition', 'completed',
      f'Batch fix: {total_fixes} India faith tags (Jewish/Hindu/Christian→correct)'))

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total fixes: {total_fixes} ===")
print("\nFinal India faith breakdown:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='IN' GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    print(f"  {faith or 'NULL':<15} {cnt:>8,}")

# Quick verification
print("\n=== Quick verification ===")
c.execute("SELECT COUNT(*) FROM churches WHERE country='IN' AND faith='Jewish' AND LOWER(name) LIKE '%temple%' AND LOWER(name) NOT LIKE '%synagogue%'")
jewish_temples = c.fetchone()[0]
print(f"  Jewish+temple (should be 0): {jewish_temples}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='IN' AND faith='Hindu' AND LOWER(name) LIKE '%church%' AND LOWER(name) NOT LIKE '%temple church%' AND LOWER(name) NOT LIKE '%masihi mandir%'")
hindu_churches = c.fetchone()[0]
print(f"  Hindu+church (should be near 0): {hindu_churches}")

c.execute("SELECT COUNT(*) FROM churches WHERE country='IN' AND faith='Christian' AND LOWER(name) LIKE '%mandir%' AND LOWER(name) NOT LIKE '%masihi%'")
christian_mandir = c.fetchone()[0]
print(f"  Christian+mandir (should be near 0): {christian_mandir}")

conn.close()
print("\nDone!")

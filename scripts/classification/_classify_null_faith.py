"""
_classify_null_faith.py — Classify NULL-faith records in priority order.

Tier 1: Denomination → faith mapping
Tier 2: Source-based defaults (single-faith scrapers)
Tier 3: Bulk name keyword matching (all keywords at once per faith)
Tier 4: Report what's left
"""
import sqlite3, time

DB = 'churches.db'
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

def remaining():
    c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL")
    return c.fetchone()[0]

def apply(condition, faith, label):
    """Apply faith to matching NULL-faith records, return count."""
    sql = f"UPDATE churches SET faith=? WHERE faith IS NULL AND ({condition})"
    c.execute(sql, (faith,))
    cnt = c.rowcount
    if cnt:
        print(f"  {label}: {cnt:,} → {faith}")
    return cnt

def apply_multi(keywords, faith, name_col='name'):
    """Apply faith where UPPER(name) matches any keyword. Uses single UPDATE."""
    clauses = " OR ".join(f"UPPER({name_col}) LIKE '%{kw}%'" for kw in keywords)
    sql = f"UPDATE churches SET faith=? WHERE faith IS NULL AND ({clauses})"
    c.execute(sql, (faith,))
    cnt = c.rowcount
    print(f"  {faith} keywords ({len(keywords)} patterns): {cnt:,}")
    return cnt

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("TIER 1: Denomination → faith mapping")
print("=" * 60)

apply("denomination IS NOT NULL AND denomination != ''", 
      "Christian", "Has denomination tag")
conn.commit()
print(f"  → After Tier 1: {remaining():,} NULL\n")

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("TIER 2: Source-based defaults")
print("=" * 60)

CHRISTIAN_SOURCES = [
    "ag_directory", "cog_scraper", "sbc_directory",
    "churchunion_scraper", "catholic_diocese_scrape",
    "cs_directory_scraper", "masstimes_nationwide",
    "wikipedia_cathedrals", "overture_canada", "overture_mexico",
    "overture_discovery", "ou_api", "diocese_sitemap",
]
for src in CHRISTIAN_SOURCES:
    apply(f"source = '{src}'", "Christian", src)

# holy_sites_import
c.execute("""SELECT name, country FROM churches 
WHERE faith IS NULL AND source='holy_sites_import' LIMIT 10""")
hs = c.fetchall()
print(f"\n  holy_sites_import samples:")
for name, ctr in hs:
    print(f"    {(name or '')[:85]} | {ctr or ''}")

# Check if they have Wikidata IDs (Q-numbers)
c.execute("""SELECT COUNT(*) FROM churches 
WHERE faith IS NULL AND source='holy_sites_import' AND name GLOB 'Q[0-9]*'""")
q_count = c.fetchone()[0]
print(f"  Wikidata Q-IDs: {q_count}")
# Most are European holy sites → Christian
apply("source = 'holy_sites_import'", "Christian", "holy_sites_import (European holy sites)")

# csv_import — check what it is
c.execute("""SELECT name, country FROM churches 
WHERE faith IS NULL AND source='csv_import' LIMIT 10""")
ci = c.fetchall()
print(f"\n  csv_import samples:")
for name, ctr in ci:
    print(f"    {(name or '')[:85]} | {ctr or ''}")

conn.commit()
print(f"  → After Tier 2: {remaining():,} NULL\n")

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("TIER 3: Keyword matching (bulk, one UPDATE per faith)")
print("=" * 60)

# --- CHRISTIAN ---
christian_kw = [
    "CHURCH", "CHAPEL", "PARISH", "CATHEDRAL", "DIOCESE", "MINISTRY",
    "MINISTERIES", "GOSPEL", "WORSHIP",
    "TABERNACLE", "PRESBYTERIAN", "METHODIST", "BAPTIST", "LUTHERAN",
    "CATHOLIC", "ORTHODOX", "EPISCOPAL", "ANGLICAN", "PENTECOSTAL",
    "EVANGELICAL", "FELLOWSHIP", "CONGREGATION",
    "PASTOR", "REV ", "BISHOP ", "FATHER ",
    "DIOCESAN", "SEMINARY", "ARCHDIOCESE", "BASILICA", "SHRINE",
    "UMC", "AME ", "CME ",
    "RCCG", "REDEEMED CHRISTIAN", "WINNERS CHAPEL",
    "LDS ", "MORMON",
    "JEHOVAH", "SEVENTH DAY ADVENTIST", "SEVENTH-DAY ADVENTIST",
    "SDA ", "NAZARENE", "WESLEYAN", "MENNONITE", "BRETHREN",
    "QUAKER", "FRIENDS MEETING", "SALVATION ARMY",
    "VINEYARD", "CALVARY CHAPEL", "HILLSONG",
    "OUR LADY", "SACRED HEART", "HOLY CROSS", "HOLY SPIRIT",
    "CHRIST ", "CHRISTIAN", "JESUS", "YESHUA", "MESSIANIC",
    "CAMPUS CRUSADE", "INTERVARSITY", "NAVIGATORS", "YOUNG LIFE",
    "SUNDAY SCHOOL", "BIBLE ", "BIBLICAL", "SCRIPTURE",
    "PROTESTANT", "REFORMED",
    "SYNOD", "MONASTERY", "CONVENT", "ABBEY", "PRIORY", "FRIARY",
    "PAROCHIAL", "RECTORY", "VICARAGE", "PARSONAGE",
    "WORD OF GOD", "LIVING WORD", "WORD OF FAITH",
    "NEW LIFE ", "NEW HOPE ", "GRACE ", "FAITH ",
    "KINGDOM OF GOD", "ZION ", "BETHEL ", "EMMANUEL", "EBENEZER",
    "CHRIST THE",
]
apply_multi(christian_kw, "Christian")

# --- MUSLIM ---
muslim_kw = [
    "MOSQUE", "MASJID", "MUSJID", "MESCID", "MESJID",
    "ISLAMIC", "MUSLIM", "MUSLIMIN", "MUSLIMAH",
    "MADRASA", "MADRASAH", "MADRASSA", "MEDRESE",
    "JAMI ", "JAMEK",
    "MUHAMMADIYAH", "NAHDLATUL",
    "AL-ISLAM", "AL ISLAM", "AL-MU",
    "SUNDA KELAPA",
]
apply_multi(muslim_kw, "Islam")

# --- JEWISH ---
jewish_kw = [
    "SYNAGOGUE", "SYNAGOG", "SHUL",
    "BNAI", "BNEI",
    "CHABAD", "LUBAVITCH",
    "JEWISH", "JUDAISM", "JUDAICA",
    "TORAH", "KOSHER",
    "RABBINICAL", "RABBINIC",
    "AGUDATH", "AGUDAT", "AGUDAS",
    "YESHIVA", "YESHIVAH", "YESHIVOT",
    "MIKVEH", "MIKVAH",
    "KAHAL", "KEHILLA", "KEHILAT",
    "HASIDIC", "CHASIDIC",
    "HILLEL",
]
apply_multi(jewish_kw, "Jewish")

# --- BUDDHIST ---
buddhist_kw = [
    "BUDDHIST", "BUDDHISM", "BUDDHA",
    "VIHARA", "VIHARAYA",
    "SANGHA", "DHARMA",
    "PAGODA",
    "MAHAYANA", "THERAVADA", "VAJRAYANA",
    "PURE LAND",
    "SHAOLIN", "BODHI",
    "NICHIREN", "SOKA GAKKAI",
    "KARMA KAGYU", "GELUG", "NYINGMA",
    "DALAI LAMA", "LAMASERY",
    "ZEN ",
    "WAT ",
]
apply_multi(buddhist_kw, "Buddhist")

# --- HINDU ---
hindu_kw = [
    "HINDU", "MANDIR", "MANDALAM", "MANDIRAM",
    "KRISHNA", "SHIVA ", "VISHNU", "GANESH", "HANUMAN",
    "LAKSHMI", "DURGA", "SARASWATI",
    "VEDIC", "VEDANTA",
    "SWAMINARAYAN", "BAPS", "ISKCON", "ARYA SAMAJ",
    "BHAJAN", "KIRTAN",
    "BRAHMA", "BRAHMIN",
    "SHRINGERI", "DWARKA",
]
apply_multi(hindu_kw, "Hindu")

# --- SIKH ---
sikh_kw = [
    "GURDWARA", "GURUDWARA",
    "SIKH TEMPLE", "SIKH SOCIETY",
    "KHALSA",
    "SIKH",
]
apply_multi(sikh_kw, "Sikh")

# --- SHINTO ---
shinto_kw = [
    "JINJA", "JINGU", "TAISHA",
    "SHINTO",
    "HACHIMAN", "INARI",
    "MEIJI JINGU", "ISE JINGU", "IZUMO TAISHA",
    "TENMANGU",
]
apply_multi(shinto_kw, "Shinto")

# --- BAHAI ---
bahai_kw = [
    "BAHAI", "BAHA ULLAH",
]
apply_multi(bahai_kw, "Bahai")

# --- FALLBACK: overture_full default to Christian ---
# overture_full is overwhelmingly US Christian churches
apply("source = 'overture_full'", "Christian", "overture_full (default Christian)")

conn.commit()
print(f"  → After Tier 3: {remaining():,} NULL\n")

# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("TIER 4: What's left?")
print("=" * 60)

rem = remaining()
print(f"Still NULL: {rem:,}")

c.execute("""SELECT source, COUNT(*) cnt FROM churches WHERE faith IS NULL 
GROUP BY source ORDER BY cnt DESC""")
print("\nBy source:")
for src, cnt in c.fetchall():
    print(f"  {str(src)[:30]:<30} {cnt:>6,}")

c.execute("""SELECT name, source, country, city FROM churches 
WHERE faith IS NULL ORDER BY RANDOM() LIMIT 60""")
print("\nRandom remaining samples:")
for name, src, ctr, city in c.fetchall():
    n = (name or '')[:85]
    print(f"  {n:<85} | {str(src)[:22]:<22} | {str(ctr or ''):<4} | {str(city or ''):<15}")

# ── Log one provenance entry ─────────────────────────────────
c.execute("""INSERT INTO provenance_log (church_id, source, action, timestamp, details)
SELECT NULL, '_classify_null_faith', 'classified', datetime('now'), 
       'Bulk faith classification via denomination mapping, source defaults, and name keywords. Started with 53303 NULL.'""")

conn.commit()
conn.close()
print("\nDone.")

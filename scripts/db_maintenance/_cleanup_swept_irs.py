"""
Comprehensive cleanup of the 13,477 IRS records accidentally swept to Jewish.

Uses word-frequency analysis from the review:
  ministries 2,196 → Christian
  bahais 852 → Baha'i
  iglesia 766 → Christian (Spanish for 'church')
  assembly 715 → Christian (Assembly of God)
  parish 398 → Christian (Catholic/Episcopal)
  cong 352 → mix (congregation could be any faith)
  dios 333 → Christian (Spanish 'God')
  cristiana/cristiano → Christian
  templo 114 → Christian (Spanish 'temple')
  tabernacle 171 → Christian
  saint 142 → Christian (Catholic)
  bautista 137 → Christian (Baptist, Spanish)
  kollel 144 → KEEP Jewish (yeshiva study group)
  
Strategy: Fix obviously non-Jewish records. Keep Jewish subsidiaries.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

base_where = "country='US' AND source LIKE 'irs%' AND faith='Jewish' AND (religion_type IN ('unknown','other') OR religion_type IS NULL)"

def do_update(label, target_faith, extra_where, not_where=None):
    global total
    where_clause = f"{base_where} AND ({extra_where})"
    if not_where:
        where_clause += f" AND NOT ({not_where})"
    c.execute(f"UPDATE churches SET faith=?, faith_tradition=? WHERE {where_clause}",
              (target_faith, target_faith))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount}")
        total += c.rowcount

print("=== Fixing obviously non-Jewish records ===\n")

# ── Christian: 'ministries' ─────────────────────────────────────────────────
do_update("ministries → Christian", "Christian",
    "(LOWER(name) LIKE '%ministries%' OR LOWER(name) LIKE '%ministry%')"
    " AND LOWER(name) NOT LIKE '%jewish%' AND LOWER(name) NOT LIKE '%torah%'"
    " AND LOWER(name) NOT LIKE '%israel%' AND LOWER(name) NOT LIKE '%hebrew%'")

# ── Baha'i ──────────────────────────────────────────────────────────────────
do_update("bahai → Baha'i", "Bahai",
    "LOWER(name) LIKE '%bahai%' OR LOWER(name) LIKE '%baha i%'")

# ── Christian: Spanish church names ─────────────────────────────────────────
do_update("iglesia (Spanish church) → Christian", "Christian",
    "LOWER(name) LIKE '%iglesia%'")

do_update("dios/cristiana/cristiano → Christian", "Christian",
    "(LOWER(name) LIKE '% dios %' OR LOWER(name) LIKE '%cristiana%'"
    " OR LOWER(name) LIKE '%cristiano%' OR LOWER(name) LIKE '%cristo%')")

do_update("templo → Christian", "Christian",
    "LOWER(name) LIKE '%templo%'")

do_update("bautista → Christian", "Christian",
    "LOWER(name) LIKE '%bautista%'")

# ── Christian: 'parish' (Catholic/Episcopal) ────────────────────────────────
do_update("parish → Christian", "Christian",
    "LOWER(name) LIKE '%parish%'"
    " AND LOWER(name) NOT LIKE '%jewish%' AND LOWER(name) NOT LIKE '%hebrew%'")

# ── Christian: 'saint' / 'st. ' ─────────────────────────────────────────────
do_update("saint/st. → Christian", "Christian",
    "(LOWER(name) LIKE '%saint%' OR LOWER(name) LIKE '%st. %' OR LOWER(name) LIKE '%st %')"
    " AND LOWER(name) NOT LIKE '%jewish%' AND LOWER(name) NOT LIKE '%israel%'")

# ── Christian: 'assembly' (Assembly of God, etc.) ───────────────────────────
do_update("assembly → Christian", "Christian",
    "(LOWER(name) LIKE '%assembly of god%' OR LOWER(name) LIKE '%assembly%')"
    " AND LOWER(name) NOT LIKE '%spiritual assembly%'")  # Baha'i uses this

# ── Baha'i: 'spiritual assembly' ────────────────────────────────────────────
do_update("spiritual assembly → Bahai", "Bahai",
    "LOWER(name) LIKE '%spiritual assembly%'")

# ── Christian: 'tabernacle' ─────────────────────────────────────────────────
do_update("tabernacle → Christian", "Christian",
    "LOWER(name) LIKE '%tabernacle%'")

# ── Christian: 'salvation army' ────────────────────────────────────────────
do_update("salvation army → Christian", "Christian",
    "LOWER(name) LIKE '%salvation army%'")

# ── Christian: 'chapel' ─────────────────────────────────────────────────────
do_update("chapel → Christian", "Christian",
    "LOWER(name) LIKE '%chapel%'")

# ── Christian: 'cathedral'/'basilica' ───────────────────────────────────────
do_update("cathedral/basilica → Christian", "Christian",
    "LOWER(name) LIKE '%cathedral%' OR LOWER(name) LIKE '%basilica%'")

# ── Christian: 'sda' (Seventh-day Adventist) ───────────────────────────────
do_update("SDA/adventist → Christian", "Christian",
    "LOWER(name) LIKE '%sda%' OR LOWER(name) LIKE '%adventist%'"
    " OR LOWER(name) LIKE '%seventh day%'")

# ── Christian: 'baptist' ───────────────────────────────────────────────────
do_update("baptist → Christian", "Christian",
    "LOWER(name) LIKE '%baptist%'")

# ── Christian: 'methodist'/'lutheran'/'presbyterian'/'episcopal' ──────────
do_update("denominations → Christian", "Christian",
    "(LOWER(name) LIKE '%methodist%' OR LOWER(name) LIKE '%lutheran%'"
    " OR LOWER(name) LIKE '%presbyterian%' OR LOWER(name) LIKE '%episcopal%'"
    " OR LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%orthodox%'"
    " OR LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%nazarene%'"
    " OR LOWER(name) LIKE '%reformed%' OR LOWER(name) LIKE '%holiness%')")

# ── Christian: 'gospel'/'evangel'/'jesus'/'christ' ────────────────────────
do_update("gospel/jesus/christ → Christian", "Christian",
    "(LOWER(name) LIKE '%gospel%' OR LOWER(name) LIKE '%evangel%'"
    " OR LOWER(name) LIKE '%jesus%' OR LOWER(name) LIKE '%christ %'"
    " OR LOWER(name) LIKE '%christian%' OR LOWER(name) LIKE '%messiah%'"
    " OR LOWER(name) LIKE '%bible%')"
    " AND LOWER(name) NOT LIKE '%jewish%'")

# ── Christian: 'church' ────────────────────────────────────────────────────
do_update("church → Christian", "Christian",
    "LOWER(name) LIKE '%church%' AND LOWER(name) NOT LIKE '%jewish%'"
    " AND LOWER(name) NOT LIKE '%hebrew%' AND LOWER(name) NOT LIKE '%torah%'")

# ── Christian: 'pastor'/'rev ' ──────────────────────────────────────────────
do_update("pastor/rev → Christian", "Christian",
    "LOWER(name) LIKE '%pastor%' OR LOWER(name) LIKE '%rev %' OR LOWER(name) LIKE '%rev.%'")

# ── Christian: 'worship' ───────────────────────────────────────────────────
do_update("worship → Christian", "Christian",
    "LOWER(name) LIKE '%worship%' AND LOWER(name) NOT LIKE '%jewish%'")

# ── Hindu/Sikh: 'temple' but not Jewish ────────────────────────────────────
do_update("temple (non-Jewish) → Hindu", "Hindu",
    "(LOWER(name) LIKE '%temple%' OR LOWER(name) LIKE '%mandir%')"
    " AND LOWER(name) NOT LIKE '%jewish%' AND LOWER(name) NOT LIKE '%synagogue%'"
    " AND LOWER(name) NOT LIKE '%hebrew%' AND LOWER(name) NOT LIKE '%israel%'"
    " AND LOWER(name) NOT LIKE '%christian%' AND LOWER(name) NOT LIKE '%church%'")

# ── Muslim: 'mosque'/'masjid'/'islam' ──────────────────────────────────────
do_update("islam/mosque → Islam", "Islam",
    "LOWER(name) LIKE '%islam%' OR LOWER(name) LIKE '%muslim%'"
    " OR LOWER(name) LIKE '%mosque%' OR LOWER(name) LIKE '%masjid%'"
    " OR LOWER(name) LIKE '%quran%' OR LOWER(name) LIKE '%mohammed%'")

# ── Buddhist ───────────────────────────────────────────────────────────────
do_update("buddhist → Buddhist", "Buddhist",
    "LOWER(name) LIKE '%buddhist%' OR LOWER(name) LIKE '%buddha%'"
    " OR LOWER(name) LIKE '%zen%' OR LOWER(name) LIKE '%dharma%'")

# ── Sikh ────────────────────────────────────────────────────────────────────
do_update("sikh/gurdwara → Sikh", "Sikh",
    "LOWER(name) LIKE '%sikh%' OR LOWER(name) LIKE '%gurdwara%'")

conn.commit()

# ── Now: remaining genuinely Jewish subsidiaries ────────────────────────────
# These should stay Jewish with religion_type='jewish_org'
print("\n=== Tagging remaining Jewish subsidiaries ===")

# Tag mikvahs as jewish_org
c.execute(f"""
    UPDATE churches SET religion_type='jewish_org'
    WHERE {base_where}
      AND (LOWER(name) LIKE '%mikvah%' OR LOWER(name) LIKE '%mikveh%'
           OR LOWER(name) LIKE '%kollel%' OR LOWER(name) LIKE '%yeshiva%'
           OR LOWER(name) LIKE '%gemach%' OR LOWER(name) LIKE '%gmach%'
           OR LOWER(name) LIKE '%chevra kadisha%' OR LOWER(name) LIKE '%chesed%'
           OR LOWER(name) LIKE '%tzedakah%' OR LOWER(name) LIKE '%bikur cholim%'
           OR LOWER(name) LIKE '%hatzalah%')
""")
print(f"  Tagged jewish_org subsidiaries: {c.rowcount}")

conn.commit()

# ── Summary ─────────────────────────────────────────────────────────────────
print(f"\n=== Total faith fixes: {total} ===\n")

print("IRS records — final faith breakdown:")
c.execute("SELECT faith, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' GROUP BY faith ORDER BY COUNT(*) DESC")
for faith, cnt in c.fetchall():
    print(f"  {str(faith):<15} {cnt:>8,}")

print("\nIRS Jewish — religion_type:")
c.execute("SELECT religion_type, COUNT(*) FROM churches WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish' GROUP BY religion_type ORDER BY COUNT(*) DESC")
for rt, cnt in c.fetchall():
    print(f"  {str(rt):<20} {cnt:>6,}")

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_cleanup_swept_irs.py', TS, TS,
      total, 0, 'faith,faith_tradition,religion_type', 'completed',
      f'Comprehensive cleanup: {total} IRS records reclassified by name patterns'))

conn.commit()
conn.close()
print("\nDone!")

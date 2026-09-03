"""
Fix IRS Jewish non-profit misclassifications.

Strategy:
  1. Use existing religion_type data to fix faith (religion_type already has 
     better classification for many records)
  2. For genuinely Jewish non-synagogue orgs, distinguish them from synagogues
     by setting religion_type appropriately
  3. Fix the 1,031 clearly Christian orgs tagged as Jewish
"""
import sqlite3
import datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

total_fixes = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Fix faith based on existing religion_type data
#    religion_type already has better classification for many IRS records
# ═══════════════════════════════════════════════════════════════════════════════
print("=== 1. Fixing faith to match religion_type ===")

faith_map = {
    'christian': 'Christian',
    'muslim': 'Islam',
    'hindu': 'Hindu',
    'buddhist': 'Buddhist',
    'sikh': 'Sikh',
    'humanist': 'Hindu',  # closest fit, or could leave
}

for rel_type, target_faith in faith_map.items():
    c.execute("""
        UPDATE churches SET faith=?, faith_tradition=?
        WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
          AND religion_type=?
    """, (target_faith, target_faith, rel_type))
    if c.rowcount > 0:
        print(f"  religion_type={rel_type} → faith={target_faith}: {c.rowcount}")
        total_fixes += c.rowcount

# Also fix 'other' and 'unknown' where names clearly indicate non-Jewish
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND religion_type IN ('other', 'unknown')
      AND (LOWER(name) LIKE '%church%' OR LOWER(name) LIKE '%assembly of god%'
           OR LOWER(name) LIKE '%baptist%' OR LOWER(name) LIKE '%gospel%'
           OR LOWER(name) LIKE '%jesus%' OR LOWER(name) LIKE '%apostolic%'
           OR LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%methodist%'
           OR LOWER(name) LIKE '%lutheran%' OR LOWER(name) LIKE '%presbyterian%'
           OR LOWER(name) LIKE '%episcopal%' OR LOWER(name) LIKE '%pentecostal%')
""")
if c.rowcount > 0:
    print(f"  religion_type=other/unknown + Christian name → Christian: {c.rowcount}")
    total_fixes += c.rowcount

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. For genuinely Jewish non-synagogue orgs, set religion_type to distinguish
#    them from actual synagogues
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 2. Tagging Jewish non-synagogue orgs ===")

# Synagogue indicators (strong synagogue signal)
synagogue_indicators = [
    "%synagogue%", "%temple%", "%shul%",
    "%congregation%", "%cong%",
    "%chabad%", "%beit%", "%beth%", "%bais%", "%knesset%",
    "%minyan%", "%kehillat%", "%kehillah%", "%kehilas%",
    "%shtiebel%", "%shtibl%",
]

# Build synagogue WHERE
syn_where = " OR ".join([f"LOWER(name) LIKE '{k}'" for k in synagogue_indicators])
non_syn_where = " AND ".join([f"LOWER(name) NOT LIKE '{k}'" for k in synagogue_indicators])

# Tag synagogues
c.execute(f"""
    UPDATE churches SET religion_type='synagogue'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND ({syn_where})
      AND religion_type IN ('jewish', 'unknown', NULL, 'other')
""")
print(f"  Tagged 'synagogue': {c.rowcount}")

# Tag non-synagogue Jewish orgs (yeshivas, charities, etc.)
c.execute(f"""
    UPDATE churches SET religion_type='jewish_org'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND ({non_syn_where})
      AND religion_type IN ('jewish', 'unknown', NULL, 'other')
""")
print(f"  Tagged 'jewish_org': {c.rowcount}")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Additional cleanup: Christian-named orgs we may have missed
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== 3. Additional Christian name cleanup ===")

# Organizations with "ministries" that aren't clearly Jewish
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity', religion_type='christian'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND LOWER(name) LIKE '%ministries%'
      AND LOWER(name) NOT LIKE '%jewish%'
      AND LOWER(name) NOT LIKE '%torah%'
      AND LOWER(name) NOT LIKE '%chabad%'
""")
if c.rowcount > 0:
    print(f"  'Ministries' → Christian: {c.rowcount}")
    total_fixes += c.rowcount

# "Fellowship" orgs that aren't Jewish
c.execute("""
    UPDATE churches SET faith='Christian', faith_tradition='Christianity', religion_type='christian'
    WHERE country='US' AND faith='Jewish' AND source LIKE 'irs%'
      AND LOWER(name) LIKE '%fellowship%'
      AND LOWER(name) NOT LIKE '%jewish%'
      AND LOWER(name) NOT LIKE '%hebrew%'
""")
if c.rowcount > 0:
    print(f"  'Fellowship' → Christian: {c.rowcount}")
    total_fixes += c.rowcount

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Log
# ═══════════════════════════════════════════════════════════════════════════════
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_fix_irs_jewish_nonprofits.py', TS, TS,
      total_fixes, 0, 'faith,faith_tradition,religion_type', 'completed',
      f'Fixed {total_fixes} IRS Jewish records: faith corrections + synagogue/jewish_org tagging'))

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total faith fixes: {total_fixes} ===")

print("\nIRS Jewish records — new faith breakdown:")
c.execute("""
    SELECT faith, COUNT(*) FROM churches 
    WHERE country='US' AND source LIKE 'irs%' AND faith IN ('Jewish', 'Christian', 'Islam', 'Hindu')
    GROUP BY faith ORDER BY COUNT(*) DESC
""")
for faith, cnt in c.fetchall():
    print(f"  {faith:<15} {cnt:>6,}")

print("\nIRS Jewish records — religion_type breakdown:")
c.execute("""
    SELECT religion_type, COUNT(*) FROM churches 
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
    GROUP BY religion_type ORDER BY COUNT(*) DESC
""")
for rt, cnt in c.fetchall():
    print(f"  {str(rt):<20} {cnt:>6,}")

conn.close()
print("\nDone!")

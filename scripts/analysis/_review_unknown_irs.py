"""
Review the ~14K IRS records accidentally swept to Jewish (religion_type='unknown'/'other').
Check for:
  1. Address matches to known houses of worship (same address = shared location)
  2. Shared personnel via org_officers or church_staff
  3. Determine which are secular vs religious subsidiaries
"""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# ── Get the problematic records ─────────────────────────────────────────────
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
""")
total_unknown = c.fetchone()[0]
print(f"Unknown/other/NULL religion_type IRS Jewish: {total_unknown:,}")

# ── 1. Check address overlap with known houses of worship ───────────────────
print("\n=== 1. Address match: 'unknown' Jewish records sharing address with any worship site ===")

c.execute("""
    SELECT COUNT(DISTINCT u.id) 
    FROM churches u
    JOIN churches w ON u.address = w.address 
        AND u.city = w.city AND u.state = w.state
        AND u.id != w.id
    WHERE u.country='US' AND u.source LIKE 'irs%' AND u.faith='Jewish'
      AND (u.religion_type IN ('unknown','other') OR u.religion_type IS NULL)
      AND u.address IS NOT NULL AND u.address != ''
      AND w.address IS NOT NULL AND w.address != ''
""")
addr_match_count = c.fetchone()[0]
print(f"  Records sharing address with another church: {addr_match_count:,}")

# Show samples of address matches
c.execute("""
    SELECT u.name, u.city, u.state, u.address,
           w.name, w.faith, w.denomination
    FROM churches u
    JOIN churches w ON u.address = w.address 
        AND u.city = w.city AND u.state = w.state
        AND u.id != w.id
    WHERE u.country='US' AND u.source LIKE 'irs%' AND u.faith='Jewish'
      AND (u.religion_type IN ('unknown','other') OR u.religion_type IS NULL)
      AND u.address IS NOT NULL AND u.address != ''
      AND w.address IS NOT NULL AND w.address != ''
    LIMIT 20
""")
print("\nSample address matches:")
for u_name, u_city, u_state, addr, w_name, w_faith, w_denom in c.fetchall():
    print(f"  '{str(u_name)[:45]:<45} → '{str(w_name)[:40]:<40} | {str(w_faith):<10} {str(w_denom or '')[:30]} | {str(addr or '')[:40]} | {str(u_city or '')}, {str(u_state or '')}")

# ── 2. Check org_officers for shared personnel ──────────────────────────────
print("\n=== 2. Shared personnel via org_officers ===")

# First check what org_officers looks like
c.execute("SELECT COUNT(*) FROM org_officers")
print(f"  org_officers total rows: {c.fetchone()[0]:,}")

c.execute("PRAGMA table_info(org_officers)")
cols = [r[1] for r in c.fetchall()]
print(f"  Columns: {cols}")

# Check if org_officers links to churches
if 'church_id' in cols:
    c.execute("""
        SELECT COUNT(DISTINCT u.id)
        FROM churches u
        JOIN org_officers o ON o.church_id = u.id
        WHERE u.country='US' AND u.source LIKE 'irs%' AND u.faith='Jewish'
          AND (u.religion_type IN ('unknown','other') OR u.religion_type IS NULL)
    """)
    officer_match = c.fetchone()[0]
    print(f"  Unknown records with personnel in org_officers: {officer_match:,}")

# ── 3. Check church_staff ───────────────────────────────────────────────────
print("\n=== 3. Shared personnel via church_staff ===")
c.execute("PRAGMA table_info(church_staff)")
cols2 = [r[1] for r in c.fetchall()]
print(f"  Columns: {cols2}")

c.execute("SELECT COUNT(*) FROM church_staff")
print(f"  church_staff total rows: {c.fetchone()[0]:,}")

# ── 4. Look for EIN matches (same EIN = same org, different listing) ───────
print("\n=== 4. EIN overlap ===")
c.execute("""
    SELECT COUNT(DISTINCT u.id)
    FROM churches u
    JOIN churches w ON u.ein = w.ein AND u.id != w.id
    WHERE u.country='US' AND u.source LIKE 'irs%' AND u.faith='Jewish'
      AND (u.religion_type IN ('unknown','other') OR u.religion_type IS NULL)
      AND u.ein IS NOT NULL AND u.ein != ''
      AND w.ein IS NOT NULL AND w.ein != ''
""")
ein_match = c.fetchone()[0]
print(f"  Unknown records sharing EIN with another church: {ein_match:,}")

if ein_match > 0:
    c.execute("""
        SELECT u.name, u.city, u.state, u.ein,
               w.name, w.faith, w.denomination
        FROM churches u
        JOIN churches w ON u.ein = w.ein AND u.id != w.id
        WHERE u.country='US' AND u.source LIKE 'irs%' AND u.faith='Jewish'
          AND (u.religion_type IN ('unknown','other') OR u.religion_type IS NULL)
          AND u.ein IS NOT NULL AND u.ein != ''
        LIMIT 15
    """)
    print("\nSample EIN matches:")
    for u_name, u_city, u_state, ein, w_name, w_faith, w_denom in c.fetchall():
        print(f"  '{str(u_name)[:40]:<40} EIN={ein} → '{str(w_name)[:40]:<40} | {w_faith}")

# ── 5. Sample of the 'unknown' records to understand what they are ──────────
print("\n=== 5. Sample of unknown religious_type ===")
c.execute("""
    SELECT name, city, state, ntee_code, ein
    FROM churches
    WHERE country='US' AND source LIKE 'irs%' AND faith='Jewish'
      AND (religion_type IN ('unknown','other') OR religion_type IS NULL)
    ORDER BY RANDOM() LIMIT 30
""")
for name, city, state, ntee, ein in c.fetchall():
    print(f"  {str(name)[:65]:<65} | {str(city or ''):<15} | {str(state or ''):<4} | NTEE={str(ntee or '')[:8]} | EIN={str(ein or '')[:12]}")

conn.close()

#!/usr/bin/env python3
"""
Fix Hindu entries that are clearly misclassified.

Main finding: holy_sites_import tagged thousands of Christian churches
as faith=Hindu because landmark_type='temple' was too broad. Many
Catalan/Spanish/Italian churches (esglesia, iglesia, chiesa, saint, etc.)
got swept in.

This script handles the obvious cases: entries with clearly Christian
names (church, iglesia, saint, etc.) from holy_sites_import that were
tagged Hindu.
"""
import sqlite3, re

conn = sqlite3.connect(r'E:\grid\churches.db')
conn.create_function("REGEXP", 2, lambda e, i: 1 if i and re.search(e, str(i), re.I) else 0)
cur = conn.cursor()
cur.execute("PRAGMA busy_timeout=30000")

def run(label, sql, params=None):
    cur.execute(sql, params or ())
    n = cur.rowcount
    if n:
        print(f"  {label}: {n:,}")
    conn.commit()
    return n

# Track totals
total = 0

# ── 1. Christian church names from holy_sites_import ──────
print("=" * 60)
print("Christian church names from holy_sites_import")
print("=" * 60)

# These are overwhelmingly Christian — "església de Sant..." = Catalan for "church of Saint..."
run("Iglesia/esglesia in name", """
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Hindu' AND country != 'IN'
    AND (name LIKE '%iglesia%' OR name LIKE '%igreja%' 
         OR name LIKE '%església%' OR name LIKE '%chiesa%'
         OR name LIKE '%kirche%' OR name LIKE '%kirk%')
    AND name NOT LIKE '%mandir%' AND name NOT LIKE '%sanatan%'
    AND landmark_type = 'temple'
""")

# "Church of", "Saint", "St. " in name — Christian unless there are Hindu context clues
run("Church/Saint in name (no Hindu keywords)", """
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Hindu' AND country != 'IN'
    AND (name LIKE '%church%' OR name LIKE '%saint%' OR name LIKE '%st. %'
         OR name LIKE '%chapel%' OR name LIKE '%cathedral%'
         OR name LIKE '%basilica%' OR name LIKE '%abbey%'
         OR name LIKE '%jesus%' OR name LIKE '%christ%'
         OR name LIKE '%catholic%' OR name LIKE '%cristo%'
         OR name LIKE '%parish%' OR name LIKE '%parroquia%'
         OR name LIKE '%mission%' OR name LIKE '%monastery%'
         OR name LIKE '%lutheran%' OR name LIKE '%baptist%'
         OR name LIKE '%methodist%' OR name LIKE '%presbyterian%'
         OR name LIKE '%pentecostal%' OR name LIKE '%anglican%'
         OR name LIKE '%evangelical%' OR name LIKE '%mennonite%'
         OR name LIKE '%jesuit%')
    AND name NOT LIKE '%mandir%' AND name NOT LIKE '%sanatan%'
    AND name NOT LIKE '%sanskrit%' AND name NOT LIKE '%krishna%'
    AND name NOT LIKE '%shiva%' AND name NOT LIKE '%hanuman%'
    AND name NOT LIKE '%ram%' AND name NOT LIKE '%murugan%'
    AND name NOT LIKE '%devi%' AND name NOT LIKE '%durga%'
    AND name NOT LIKE '%guru%' AND name NOT LIKE '%hindu%'
    AND name NOT LIKE '%vedic%' AND name NOT LIKE '%yoga%'
    AND name NOT LIKE '%yogi%' AND name NOT LIKE '%brahma%'
    AND name NOT LIKE '%ayurved%'
""")

# ── 2. "San"/"Santo"/"Santa" in Spanish/Portuguese countries ──
# "San" is Spanish for "Saint" — will catch some false positives
# but "San" also appears in "Sanatan" (legitimate Hindu term)
print("\n" + "=" * 60)
print('"San/Santo/Santa" in Latin American / European countries')
print("=" * 60)

run("San/Santo/Santa in name (Spanish/Portuguese context)", """
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Hindu' AND country != 'IN'
    AND country IN ('ES', 'MX', 'AR', 'CO', 'PE', 'VE', 'CL', 'EC', 'GT',
                    'CU', 'DO', 'BO', 'SV', 'HN', 'PY', 'NI', 'CR', 'PA',
                    'UY', 'GQ', 'PR', 'PH', 'AD')
    AND name REGEXP '\\bSan\\b|\\bSanto\\b|\\bSanta\\b'
    AND name NOT LIKE '%mandir%' AND name NOT LIKE '%sanatan%'
    AND name NOT LIKE '%sanskrit%' AND name NOT LIKE '%krishna%'
    AND name NOT LIKE '%shiva%' AND name NOT LIKE '%hanuman%'
    AND name NOT LIKE '%guru%' AND name NOT LIKE '%hindu%'
    AND landmark_type = 'temple'
""")

# ── 3. Most AD (Andorra) entries ──
run("Andorra (all Catalan churches)", """
    UPDATE churches SET faith='Christian', faith_tradition='Christian'
    WHERE faith='Hindu' AND country = 'AD'
""")

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

hindu_now = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu'").fetchone()[0]
hindu_in = cur.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND country='IN'").fetchone()[0]
hindu_out = hindu_now - hindu_in
print(f"Hindu total: {hindu_now:,}")
print(f"  In India: {hindu_in:,}")
print(f"  Outside India: {hindu_out:,}")

print(f"\nTop 15 non-India countries:")
for r in cur.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches WHERE faith='Hindu' AND country != 'IN'
    GROUP BY country ORDER BY cnt DESC LIMIT 15
"""):
    print(f"  {r[0]:30s} {r[1]:>8,}")

conn.close()

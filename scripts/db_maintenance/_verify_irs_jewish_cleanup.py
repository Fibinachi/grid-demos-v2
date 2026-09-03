#!/usr/bin/env python3
"""
_verify_irs_jewish_cleanup.py — Verify IRS Jewish entries are clean.

Checks all 6,099 IRS-sourced Jewish entries for misclassification signals:
- Christian landmark types
- Christian name patterns
- Wrong-denomination flags
- Previously-fixed entries
"""
import sqlite3, sys
from datetime import datetime, timezone

DB = "churches.db"
conn = sqlite3.connect(f"E:\\grid\\{DB}", timeout=60)
c = conn.cursor()

print("=" * 60)
print("IRS Jewish Cleanup Verification")
print("=" * 60)

# ── Category 1: Christian landmark_types ──
print("\n1. Christian landmark_type check...")
CHRISTIAN_LT = ('church', 'cathedral', 'chapel', 'basilica', 'parish', 
                'monastery', 'convent', 'rectory', 'abbey', 'shrine_christian',
                'mission', 'diocese_office', 'archdiocese')
placeholders = ','.join('?' for _ in CHRISTIAN_LT)
c.execute(f"""SELECT COUNT(*) FROM churches 
WHERE faith='Judaism' AND source LIKE '%irs%' 
AND landmark_type IN ({placeholders})""", CHRISTIAN_LT)
count = c.fetchone()[0]
print(f"  {'✅ CLEAN' if count == 0 else f'❌ {count} FOUND'}: {count}")

# ── Category 2: Christian name patterns ──
print("\n2. Christian name patterns...")
checks = {
    'CHURCH': "%CHURCH%",
    'CHAPEL': "%CHAPEL%",
    'CATHEDRAL': "%CATHEDRAL%",
    'MINISTRY': "%MINISTR%",
    'FELLOWSHIP': "%FELLOWSHIP%",
    'DIOCESE': "%DIOCESE%",
    'PARISH': "%PARISH%",
    'PRESBYTERIAN': "%PRESBYTERIAN%",
    'METHODIST': "%METHODIST%",
    'LUTHERAN': "%LUTHERAN%",
    'BAPTIST': "%BAPTIST%",
    'CATHOLIC': "%CATHOLIC%",
    'EPISCOPAL': "%EPISCOPAL%",
    'PENTECOSTAL': "%PENTECOSTAL%",
    'ASSEMBLY OF GOD': "%ASSEMBLY OF GOD%",
    'GOSPEL': "%GOSPEL%",
    'EVANGELICAL': "%EVANGELICAL%",
    'CHRISTIAN': "%CHRISTIAN%",
    'JESUS': "%JESUS%",
}
all_clean = True
for label, pattern in checks.items():
    c.execute("""SELECT COUNT(*) FROM churches 
    WHERE faith='Judaism' AND source LIKE '%irs%' AND name LIKE ?""", (pattern,))
    count = c.fetchone()[0]
    status = "✅" if count == 0 else "❌"
    if count > 0:
        all_clean = False
    print(f"  {status} {label}: {count}")

# ── Category 3: Muslim patterns ──
print("\n3. Muslim name patterns...")
muslim_checks = {
    'MOSQUE': "%MOSQUE%",
    'MASJID': "%MASJID%",
    'ISLAMIC': "%ISLAMIC%",
    'MUSLIM': "%MUSLIM%",
}
for label, pattern in muslim_checks.items():
    c.execute("""SELECT COUNT(*) FROM churches 
    WHERE faith='Judaism' AND source LIKE '%irs%' AND name LIKE ?""", (pattern,))
    count = c.fetchone()[0]
    status = "✅" if count == 0 else "❌"
    if count > 0:
        all_clean = False
    print(f"  {status} {label}: {count}")

# ── Category 4: Jewish landmark_type consistency ──
print("\n4. IRS Jewish landmark_type distribution (sanity check)...")
c.execute("""SELECT landmark_type, COUNT(*) FROM churches 
WHERE faith='Judaism' AND source LIKE '%irs%' 
GROUP BY landmark_type ORDER BY COUNT(*) DESC""")
for lt, cnt in c.fetchall():
    print(f"  {lt}: {cnt:,}")

# ── Category 5: Cross-check non-Jewish IRS with Jewish markers ──
print("\n5. Non-Jewish IRS entries with Jewish landmark_types (should be fixed)...")
JEWISH_LT = ('synagogue', 'chabad_house', 'yeshiva', 'mikveh', 'kollel', 'beit_midrash')
placeholders2 = ','.join('?' for _ in JEWISH_LT)
c.execute(f"""SELECT faith, landmark_type, COUNT(*) FROM churches 
WHERE source LIKE '%irs%' AND faith != 'Judaism' 
AND landmark_type IN ({placeholders2})
GROUP BY faith, landmark_type ORDER BY COUNT(*) DESC""", JEWISH_LT)
rows = c.fetchall()
if rows:
    print("  Remaining (may be legitimate non-denom orgs in Jewish buildings):")
    for faith, lt, cnt in rows:
        print(f"    {faith} / {lt}: {cnt}")
else:
    print("  ✅ None remaining")

# ── Category 6: Count by source ──
print("\n6. IRS source breakdown...")
c.execute("""SELECT source, COUNT(*) FROM churches 
WHERE faith='Judaism' AND source LIKE '%irs%' 
GROUP BY source ORDER BY COUNT(*) DESC""")
for src, cnt in c.fetchall():
    print(f"  {src}: {cnt:,}")

# ── CHAPEL deep-dive ──
c.execute("""SELECT id, name, city, state, landmark_type, tradition 
FROM churches WHERE faith='Judaism' AND source LIKE '%irs%' AND name LIKE '%CHAPEL%'""")
chapel_rows = c.fetchall()
if chapel_rows:
    print("\n  CHAPEL entries detail:")
    for r in chapel_rows:
        print(f"    #{r[0]}: {r[1]} | {r[2]}, {r[3]} | type={r[4]} | trad={r[5]}")

# ── Final verdict ──
print("\n" + "=" * 60)
if all_clean:
    print("VERDICT: ✅ IRS Jewish entries are CLEAN — no misclassifications found.")
else:
    print("VERDICT: ❌ Issues found — see above for details.")
print(f"Total IRS-sourced Judaism entries: {c.execute('SELECT COUNT(*) FROM churches WHERE faith=\"Judaism\" AND source LIKE \"%irs%\"').fetchone()[0]:,}")
print("=" * 60)

conn.close()

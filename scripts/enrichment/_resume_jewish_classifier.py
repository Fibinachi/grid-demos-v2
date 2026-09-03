#!/usr/bin/env python3
"""Resume Jewish tradition classifier from B5 REFORM_PATTERNS onward.

The first run (no REGEXP) handled B1 (Chabad), B5 first stmt, B7-B11 (LIKE).
The second run (REGEXP fix) handled B2 (Hasidic), B3 (Orthodox), B4 (Sephardic),
  but crashed during B5 REFORM_PATTERNS loop.

This script picks up at B5 REFORM_PATTERNS: B5-B11.
"""
import sqlite3, re, time

DB = "churches.db"
conn = sqlite3.connect(DB, timeout=60)

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

def where_null():
    return "(faith_tradition IS NULL OR faith_tradition IN ('Jewish','Judaism'))"

total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
print(f"Jewish entries: {total:,}")

# Count unclassified
unclass = c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND {where_null()}").fetchone()[0]
print(f"Unclassified (NULL/Jewish/Judaism): {unclass:,}")

# ═══════════════════════════════════════════════════
# B5: Reform (REFORM_PATTERNS loop — REGEXP)
# ═══════════════════════════════════════════════════
print("\n--- B5: Reform (REGEXP patterns) ---")
REFORM_PATTERNS = [
    (r'\breform\b', 'Reform keyword'),
    (r'\bliberal\s+jewish\b', 'Liberal Judaism'),
    (r'\bprogressive\s+jewish\b', 'Progressive Judaism'),
    (r'\btemple\s+(beth|bet|b[`\']?nai|shalom|emanuel|emmanuel|israel|sinai|judea|zion|sholom|aharoh|am|avodah|chai|dorah|eliyah|haverim|kol|menorah|shir|tikvah|yisrael)\b', 'Temple (Reform/Conserv)'),
    (r'\bcongregation\s+(beth|bet|b[`\']?nai|shalom|emanuel|emmanuel|israel|sinai)\b', 'Congregation (likely Reform/Conserv)'),
]
for pat, group in REFORM_PATTERNS:
    c.execute(f"""
        UPDATE churches SET faith_tradition='Reform'
        WHERE faith='Jewish' AND {where_null()}
        AND name REGEXP ?
        AND name NOT LIKE '%orthodox%'
        AND name NOT LIKE '%chabad%'
        AND name NOT LIKE '%sephard%'
    """, (pat,))
    log(f"Reform ({group})", c.rowcount)
conn.commit()

# ═══════════════════════════════════════════════════
# B6: Conservative (REGEXP)
# ═══════════════════════════════════════════════════
print("\n--- B6: Conservative ---")
CONSERVATIVE_PATTERNS = [
    (r'\bconservative\b', 'Conservative keyword'),
    (r'\bmasorti\b', 'Masorti'),
    (r'\buscj\b', 'USCJ'),
    (r'\bunited\s+synagogue\b', 'United Synagogue'),
]
for pat, group in CONSERVATIVE_PATTERNS:
    c.execute(f"""
        UPDATE churches SET faith_tradition='Conservative'
        WHERE faith='Jewish' AND {where_null()}
        AND name REGEXP ?
    """, (pat,))
    log(f"Conservative ({group})", c.rowcount)
conn.commit()

# ═══════════════════════════════════════════════════
# B7-B8 work (LIKE — already ran in first pass but just in case)
# ═══════════════════════════════════════════════════

# B9: 'Temple' in US (remaining)
print("\n--- B9: Temple (remaining US) → Reform ---")
c.execute(f"""
    UPDATE churches SET faith_tradition='Reform'
    WHERE faith='Jewish' AND {where_null()}
    AND country='US'
    AND name LIKE '%temple%'
    AND name NOT LIKE '%chabad%'
    AND name NOT LIKE '%lubavitch%'
""")
log("US Temple (remaining)", c.rowcount)
conn.commit()

# B10: By denomination
print("\n--- B10: Denomination-based ---")
c.execute(f"""
    UPDATE churches SET faith_tradition='Orthodox'
    WHERE faith='Jewish' AND {where_null()}
    AND denomination='Jewish'
""")
log("denom=Jewish → Orthodox", c.rowcount)
conn.commit()

# B11: Default remaining → 'Judaism'
print("\n--- B11: Remaining → faith_tradition='Judaism' ---")
c.execute(f"""
    UPDATE churches SET faith_tradition='Judaism'
    WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition='')
""")
log("Default to Judaism", c.rowcount)
conn.commit()

# ═══════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
final = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish'").fetchone()[0]
print(f"Jewish entries: {final:,}")
print(f"\nJewish faith_tradition distribution:")
for r in c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Jewish' GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {str(r[0] or 'NULL'):30s} {r[1]:>8}")

conn.close()

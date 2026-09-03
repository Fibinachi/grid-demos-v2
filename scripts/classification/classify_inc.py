"""
Classify Iglesia Ni Cristo entries in PH with proper CFTLM and English translations.

INC = Iglesia Ni Cristo (Church of Christ)
- Founded 1914 by Felix Manalo
- Independent Filipino Christian denomination (nontrinitarian)
- ~1,287 entries in affected regions
- Centralized hierarchy: Central Office → Districts → Locales

CFTLM: Christian → Iglesia Ni Cristo → (district)
Name pattern: "Iglesia Ni Cristo - Lokal ng [Place]" → English: "Church of Christ - [Place] Locale"
"""

import sqlite3

db = sqlite3.connect("E:/grid/churches.db")
db.row_factory = sqlite3.Row

print("=" * 60)
print("IGLESIA NI CRISTO — CLASSIFICATION & TRANSLATION")
print("=" * 60)

# 1. Count total
cursor = db.execute("SELECT COUNT(*) FROM churches WHERE country='PH' AND name LIKE '%Iglesia Ni Cristo%' OR name LIKE '%Iglesia ni Cristo%'")
total = cursor.fetchone()[0]
print(f"\nTotal INC entries in PH: {total:,}")

# 2. Update CFTLM for all INC entries
db.execute("""
    UPDATE churches SET
        faith = 'Christian',
        tradition = 'Iglesia Ni Cristo',
        legacy = 'Iglesia Ni Cristo'
    WHERE country = 'PH'
      AND (name LIKE '%Iglesia Ni Cristo%' OR name LIKE '%Iglesia ni Cristo%')
      AND landmark_type != 'data_artifact'
""")
updated = db.execute("SELECT changes()").fetchone()[0]
print(f"CFTLM updated: {updated:,} → faith=Christian, tradition=Iglesia Ni Cristo, legacy=Iglesia Ni Cristo")

# 3. Translate names to English
# Pattern: "Iglesia Ni Cristo - Lokal ng [Place]" → "Church of Christ - [Place] Locale"
# Pattern: "Iglesia Ni Cristo" (bare) → "Church of Christ"
# Pattern: "Iglesia Ni Cristo - [District] District Office" → "Church of Christ - [District] District Office"

cursor = db.execute("""
    SELECT rowid, name FROM churches
    WHERE country = 'PH'
      AND (name LIKE '%Iglesia Ni Cristo%' OR name LIKE '%Iglesia ni Cristo%')
""")
translated = 0
for r in cursor.fetchall():
    name = r['name']
    rid = r['rowid']
    
    # Build English name
    eng = name
    eng = eng.replace('Iglesia Ni Cristo', 'Church of Christ')
    eng = eng.replace('Iglesia ni Cristo', 'Church of Christ')
    eng = eng.replace('Lokal ng', 'Locale of')
    eng = eng.replace(' - District Office', ' District Office')
    
    # Only update if translation is different
    if eng != name:
        db.execute("UPDATE churches SET name_english = ?, name_original = name WHERE rowid = ?", 
                   (eng, rid))
        translated += 1

db.commit()
print(f"English translations: {translated:,} (name → name_english, name → name_original)")

# 4. Verify
cursor = db.execute("""
    SELECT name, name_english FROM churches
    WHERE country = 'PH' AND tradition = 'Iglesia Ni Cristo'
      AND name_english IS NOT NULL
    LIMIT 10
""")
print("\nSample translations:")
for r in cursor.fetchall():
    print(f"  {r['name'][:60]}")
    print(f"    → {r['name_english'][:60]}")

# 5. Denomination stats
print("\nClassification summary:")
cursor = db.execute("""
    SELECT tradition, legacy, COUNT(*) as cnt
    FROM churches WHERE country='PH'
      AND tradition='Iglesia Ni Cristo'
    GROUP BY tradition, legacy
""")
for r in cursor.fetchall():
    print(f"  tradition={r['tradition']}  legacy={r['legacy']}  count={r['cnt']:,}")

# 6. INC is a DENOMINATION (not a megachurch)
print("\nClassification: DENOMINATION")
print("  Iglesia Ni Cristo is an independent Filipino Christian church")
print("  founded in 1914 by Felix Manalo. It is a denomination with")
print("  centralized governance — not a multi-campus megachurch.")
print("  Hierarchy: Central Office (Quezon City) → Ecclesiastical Districts → Locales")
print()

db.close()
print("Done.")

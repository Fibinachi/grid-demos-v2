"""Check Arabic-script names under Judaism - what they look like in the map."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Arabic-script names under Judaism - show original + transliterated
c.execute("""
    SELECT id, name, name_transliterated, city, country, landmark_type
    FROM churches 
    WHERE faith='Judaism' AND name GLOB '*[ء-ي]*'
    ORDER BY country, city
""")
rows = c.fetchall()
print(f"Arabic-script Jewish sites: {len(rows)}\n")
for r in rows:
    orig = str(r[1] or '')[:60]
    trans = str(r[2] or '')[:60]
    same = " ⚠️ SAME" if trans == orig else ""
    print(f"  {r[0]:>8d} | orig={orig:60s}")
    print(f"           | tran={trans:60s} | {r[3] or '?'}, {r[4] or '?'} [{r[5] or '?'}]{same}")
    print()

# Also check if there are Arabic names in name_transliterated = name
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Judaism' AND name GLOB '*[ء-ي]*' 
    AND (name_transliterated IS NULL OR name_transliterated = name)
""")
print(f"\nArabic names where transliteration = original (not transliterated): {c.fetchone()[0]}")

# Check what translit library gives
from transliterate import translit
print("\n=== Testing Arabic transliteration library ===")
c.execute("SELECT name FROM churches WHERE faith='Judaism' AND name GLOB '*[ء-ي]*' LIMIT 3")
for r in c.fetchall():
    try:
        t = translit(r[0], 'ar', reversed=True)
        print(f"  {r[0][:40]:40s} -> {t}")
    except Exception as e:
        print(f"  {r[0][:40]:40s} -> ERROR: {e}")

conn.close()

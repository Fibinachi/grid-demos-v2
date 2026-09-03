"""Summary statistics for US Jewish accuracy report"""
import sqlite3
db = sqlite3.connect('E:\\grid\\churches.db')

CORE = "faith='Jewish' AND (country='US' OR state IS NOT NULL)"

print("=== US JEWISH ACCURACY AUDIT SUMMARY ===\n")

total = db.execute(f"SELECT COUNT(*) FROM churches WHERE {CORE}").fetchone()[0]
print(f"Total US Jewish records: {total:,}")

print("\n--- CATEGORY A: LIKELY WRONG FAITH (should be Christian) ---")

# A1: Christian denominations
print("\nA1. Christian denomination:")
rows = db.execute(f"""
    SELECT denomination, COUNT(*) AS c FROM churches 
    WHERE {CORE}
    AND denomination IN ('Pentecostal Assemblies of the World','Pentecostal Church of God',
    'Seventh-day Adventist','Seventh-day Adventist Church','Southern Baptist Convention',
    'Church of God in Christ','Church of God (Holiness)','Wesleyan Church',
    'African Methodist Episcopal Church')
    GROUP BY denomination ORDER BY c DESC
""").fetchall()
for d, c in rows:
    print(f"  {d}: {c}")
a1 = sum(r[1] for r in rows)
print(f"  Total A1: {a1}")

# A2: CHRIST/JESUS in name (no Jewish keywords)
a2 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND (UPPER(name) LIKE '%JESUS%' OR UPPER(name) LIKE '%CHRIST%')
    AND UPPER(name) NOT LIKE '%CONGREGATION%'
    AND UPPER(name) NOT LIKE '%CHABAD%'
    AND UPPER(name) NOT LIKE '%BETH %'
    AND UPPER(name) NOT LIKE '%TEMPLE%'
    AND UPPER(name) NOT LIKE '%ISRAEL%'
    AND UPPER(name) NOT LIKE '%JEWISH%'
    AND UPPER(name) NOT LIKE '%SYNAGOGUE%'
""").fetchone()[0]
print(f"\nA2. CHRIST/JESUS in name (no Jewish keywords): {a2}")

# A3: JEHOVAH in name
a3 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND UPPER(name) LIKE '%JEHOV%'
""").fetchone()[0]
print(f"A3. JEHOVAH in name: {a3}")

# A4: CALVARY
a4_all = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND UPPER(name) LIKE '%CALVARY%'
""").fetchone()[0]
a4_mess = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND UPPER(name) LIKE '%CALVARY%' AND UPPER(name) LIKE '%MESSIAN%'
""").fetchone()[0]
print(f"A4. CALVARY in name: {a4_all} (messianic: {a4_mess}, likely Christian: {a4_all - a4_mess})")

# A5: Non-Denom + Christ/Jesus
a5 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND UPPER(denomination) LIKE '%NON-DENOM%'
    AND (UPPER(name) LIKE '%CHRIST%' OR UPPER(name) LIKE '%JESUS%')
""").fetchone()[0]
print(f"A5. Non-Denom/Independent + Christ/Jesus: {a5}")

# A6: MORMON
a6 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND UPPER(name) LIKE '%MORMON%'
""").fetchone()[0]
print(f"A6. MORMON in name: {a6}")

print("\n--- CATEGORY B: WRONG LANDMARK_TYPE ---")
b1 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND landmark_type='mosque'
""").fetchone()[0]
print(f"B1. lm=mosque (should be synagogue): {b1}")

b2 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND landmark_type IN ('cathedral','abbey','monastery','shrine')
    AND (UPPER(name) LIKE '%CONGREGATION%' OR UPPER(name) LIKE '%SYNAGOGUE%'
         OR UPPER(name) LIKE '%YESHIVA%' OR UPPER(name) LIKE '%CHABAD%'
         OR UPPER(name) LIKE '%BETH %' OR UPPER(name) LIKE '%TEMPLE%'
         OR UPPER(name) LIKE '%TORAH%' OR UPPER(name) LIKE '%JEWISH%'
         OR UPPER(name) LIKE '%ISRAEL%' OR UPPER(name) LIKE '%SHALOM%')
""").fetchone()[0]
print(f"B2. lm=cathedral/abbey/monastery/shrine on Jewish orgs: {b2}")

print("\n--- CATEGORY C: WRONG DENOMINATION ---")
c1 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND (UPPER(name) LIKE '%CONGREGATION%' OR UPPER(name) LIKE '%SYNAGOGUE%'
         OR UPPER(name) LIKE '%BETH %' OR UPPER(name) LIKE '%TEMPLE%'
         OR UPPER(name) LIKE '%CHABAD%' OR UPPER(name) LIKE '%YESHIVA%')
    AND UPPER(denomination) LIKE '%BAPTIST%'
""").fetchone()[0]
print(f"C1. Jewish names with Baptist denom: {c1}")

c2 = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND (UPPER(name) LIKE '%CONGREGATION%' OR UPPER(name) LIKE '%SYNAGOGUE%'
         OR UPPER(name) LIKE '%BETH %' OR UPPER(name) LIKE '%TEMPLE%'
         OR UPPER(name) LIKE '%CHABAD%' OR UPPER(name) LIKE '%YESHIVA%')
    AND UPPER(denomination) LIKE '%METHODIST%'
""").fetchone()[0]
print(f"C2. Jewish names with Methodist denom: {c2}")

# Grand total distinct flagged
print("\n=== GRAND TOTAL FLAGGED (distinct rowids) ===")
total_flagged = db.execute(f"""
    SELECT COUNT(*) FROM churches 
    WHERE {CORE}
    AND (
        denomination IN ('Pentecostal Assemblies of the World','Pentecostal Church of God',
        'Seventh-day Adventist','Seventh-day Adventist Church','Southern Baptist Convention',
        'Church of God in Christ','Church of God (Holiness)','Wesleyan Church',
        'African Methodist Episcopal Church')
        OR
        ((UPPER(name) LIKE '%JESUS%' OR UPPER(name) LIKE '%CHRIST%')
         AND UPPER(name) NOT LIKE '%CONGREGATION%'
         AND UPPER(name) NOT LIKE '%CHABAD%'
         AND UPPER(name) NOT LIKE '%BETH %'
         AND UPPER(name) NOT LIKE '%TEMPLE%'
         AND UPPER(name) NOT LIKE '%ISRAEL%'
         AND UPPER(name) NOT LIKE '%JEWISH%'
         AND UPPER(name) NOT LIKE '%SYNAGOGUE%')
        OR UPPER(name) LIKE '%JEHOV%'
        OR (UPPER(name) LIKE '%CALVARY%' AND UPPER(name) NOT LIKE '%MESSIAN%')
        OR (UPPER(denomination) LIKE '%NON-DENOM%'
            AND (UPPER(name) LIKE '%CHRIST%' OR UPPER(name) LIKE '%JESUS%'))
        OR UPPER(name) LIKE '%MORMON%'
    )
""").fetchone()[0]
print(f"Distinct flagged records: {total_flagged:,} out of {total:,} ({total_flagged/total*100:.1f}%)")
print(f"If fixed: US Jewish would be ~{total - total_flagged:,}")

db.close()

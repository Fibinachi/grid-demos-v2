"""Verify DeepSeek classification results."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect

conn = connect(r'E:\grid\churches.db')

# 1. Check the key misclassified records are now correct
print("=== KEY RECORDS ===")
checks = [
    ("CHRIST SCIENTIST", "Christian Science should be Christian"),
    ("ARCHDIOCESAN", "Archdiocesan should be Christian/Catholic"),
    ("BETH ISRAEL DEACONESS", "Beth Israel should be Judaism/hospital"),
    ("BNAI JACOB", "Synagogue should be Judaism"),
    ("CEMETERY", "Cemeteries should be tagged"),
    ("ST ", "Saint churches should be Christian"),
]

for pattern, desc in checks:
    rows = conn.execute(f"""
        SELECT id, name, faith, denomination, landmark_type
        FROM churches 
        WHERE UPPER(name) LIKE '%{pattern}%' AND state='MA' AND UPPER(city)='BOSTON'
        LIMIT 5
    """).fetchall()
    print(f"\n{desc}:")
    for r in rows:
        print(f"  #{r[0]}: {r[1][:50]} | {r[2]} | {r[3] or '-'} | {r[4]}")

# 2. Landmark type breakdown
print("\n=== LANDMARK TYPE BREAKDOWN ===")
types = conn.execute("""
    SELECT landmark_type, COUNT(*) as cnt 
    FROM churches WHERE state='MA' AND UPPER(city)='BOSTON'
    GROUP BY landmark_type ORDER BY cnt DESC
""").fetchall()
for t in types:
    print(f"  {t[0] or 'NULL'}: {t[1]}")

# 3. Judaism breakdown
print("\n=== JUDAISM IN BOSTON ===")
judaism = conn.execute("""
    SELECT id, name, landmark_type, boston_pid
    FROM churches 
    WHERE faith='Judaism' AND state='MA' AND UPPER(city)='BOSTON'
    ORDER BY name
""").fetchall()
for r in judaism:
    print(f"  #{r[0]}: {r[1][:55]} | {r[2]} | pid={r[3]}")

# 4. Cemeteries
print("\n=== CEMETERIES ===")
cems = conn.execute("""
    SELECT id, name, faith, denomination, boston_pid
    FROM churches 
    WHERE landmark_type='cemetery' AND state='MA'
    ORDER BY name
""").fetchall()
for c in cems:
    print(f"  #{c[0]}: {c[1][:55]} | {c[2]} | {c[3] or '-'} | pid={c[4]}")

# 5. Hospitals
print("\n=== HOSPITALS ===")
hosp = conn.execute("""
    SELECT id, name, faith, boston_pid
    FROM churches 
    WHERE landmark_type='hospital' AND state='MA'
    ORDER BY name
""").fetchall()
for h in hosp:
    print(f"  #{h[0]}: {h[1][:55]} | {h[2]} | pid={h[3]}")

# 6. Schools
print("\n=== SCHOOLS ===")
schools = conn.execute("""
    SELECT id, name, faith, boston_pid, boston_school_schid
    FROM churches 
    WHERE landmark_type='school' AND state='MA'
    ORDER BY name
""").fetchall()
for s in schools:
    print(f"  #{s[0]}: {s[1][:55]} | {s[2]} | pid={s[3]} | schid={s[4]}")

# 7. Top 10 highest valued properties
print("\n=== TOP 10 HIGHEST VALUE ===")
top = conn.execute("""
    SELECT id, name, faith, landmark_type, boston_property_json
    FROM churches 
    WHERE boston_property_json IS NOT NULL
    ORDER BY CAST(REPLACE(REPLACE(REPLACE(json_extract(boston_property_json, '$.total_value'), '$', ''), ',', ''), ' ', '') AS INTEGER) DESC
    LIMIT 10
""").fetchall()
for t in top:
    j = json.loads(t[4])
    val = j.get('total_value', '?')
    area = j.get('gross_area', '?')
    print(f"  ${str(val):>12}  {str(area):>8}sf  {t[1][:45]} | {t[2]} | {t[3]}")

conn.close()

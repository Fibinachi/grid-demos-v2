"""Fix classification issues in imported Boston property records."""
import sys, json
sys.path.insert(0, r'E:\grid')
from gw_db import connect, log_change

conn = connect(r'E:\grid\churches.db')

# 1. Fix 93 Falmouth St (PID=0401162000) - Christian Science trustee
rows = conn.execute("SELECT id, name, faith, boston_pid, boston_property_json FROM churches WHERE boston_pid = '0401162000'").fetchall()
for r in rows:
    church_id = r[0]
    if church_id is None:
        # Find by other means
        rows2 = conn.execute("SELECT id, name, faith FROM churches WHERE name LIKE '%ADAMS GEORGE WARDELL%'").fetchall()
        if rows2:
            church_id = rows2[0][0]
            r = rows2[0]
    if church_id:
        old_name = r[1]
        print(f"Fixing #{church_id}: {old_name}")
        conn.execute("UPDATE churches SET name = 'First Church of Christ, Scientist (Trust)', faith = 'Christian', denomination = 'Christian Science' WHERE id = ?", (church_id,))
        log_change(conn, church_id=church_id, field_name='name', old_value=old_name, new_value='First Church of Christ, Scientist (Trust)', source='boston_fix_classification')
        log_change(conn, church_id=church_id, field_name='faith', old_value=r[2], new_value='Christian', source='boston_fix_classification')

# Helper to get actual church_id even when cursor didn't return it
def find_by_pid(pid):
    rows = conn.execute("SELECT id, name, faith FROM churches WHERE boston_pid = ?", (pid,)).fetchall()
    if not rows:
        return None
    r = rows[0]
    if r[0] is None:
        # lastrowid failed during import, find by name
        rows2 = conn.execute("SELECT id, name, faith FROM churches WHERE name LIKE ? AND boston_pid = ?", (f'%{r[1][:20]}%', pid)).fetchall()
        return rows2[0] if rows2 else None
    return r

# 2. Fix PID=0401185000 - First Church of Christ, Scientist main building
r = find_by_pid('0401185000')
if r:
    church_id = r[0]
    print(f"Fixing #{church_id}: {r[1]} -> set denomination=Christian Science")
    conn.execute("UPDATE churches SET denomination = 'Christian Science' WHERE id = ?", (church_id,))

# 3. Fix Beth Israel Deaconess - already Judaism/hospital but verify
for pid in ['0401944050', '0401966001']:
    r = find_by_pid(pid)
    if r:
        print(f"  #{r[0]}: {r[1][:50]} | faith={r[2]} | pid={pid}")

# 4. General fix: any "CHRIST SCIENTIST" in name should be Christian Science  
rows = conn.execute("SELECT id, name, faith, denomination FROM churches WHERE UPPER(name) LIKE '%CHRIST SCIENTIST%'").fetchall()
for r in rows:
    if r[0] and (r[2] != 'Christian' or r[3] != 'Christian Science'):
        print(f"Fixing CS #{r[0]}: {r[1][:50]} | {r[2]}/{r[3]}")
        conn.execute("UPDATE churches SET faith = 'Christian', denomination = 'Christian Science' WHERE id = ?", (r[0],))

# 5. Count by faith for imported records
print("\n--- Imported records by faith ---")
faiths = conn.execute("SELECT faith, COUNT(*) as cnt FROM churches WHERE source='boston_property_assessment' GROUP BY faith ORDER BY cnt DESC").fetchall()
for f in faiths:
    print(f"  {f[0]}: {f[1]}")

# 6. Count by landmark_type
print("\n--- Imported records by type ---")
types = conn.execute("SELECT landmark_type, COUNT(*) as cnt FROM churches WHERE source='boston_property_assessment' GROUP BY landmark_type ORDER BY cnt DESC").fetchall()
for t in types:
    print(f"  {t[0]}: {t[1]}")

# 7. Show cemeteries
print("\n--- Cemeteries ---")
cems = conn.execute("SELECT id, name, faith, denomination, boston_pid FROM churches WHERE source='boston_property_assessment' AND landmark_type='cemetery'").fetchall()
for c in cems:
    print(f"  #{c[0]}: {c[1][:55]} | {c[2]} | {c[3] or '-'} | pid={c[4]}")

# 8. Show hospitals
print("\n--- Hospitals ---")
hosp = conn.execute("SELECT id, name, faith, boston_pid FROM churches WHERE source='boston_property_assessment' AND landmark_type='hospital'").fetchall()
for h in hosp:
    print(f"  #{h[0]}: {h[1][:55]} | {h[2]} | pid={h[3]}")

# 9. Show a few top-value records
print("\n--- Top 10 by total value ---")
top = conn.execute("""
    SELECT id, name, faith, landmark_type, boston_property_json
    FROM churches 
    WHERE source='boston_property_assessment'
      AND boston_property_json IS NOT NULL
    ORDER BY CAST(REPLACE(REPLACE(REPLACE(json_extract(boston_property_json, '$.total_value'), '$', ''), ',', ''), ' ', '') AS INTEGER) DESC
    LIMIT 10
""").fetchall()
for t in top:
    j = json.loads(t[4])
    val = j.get('total_value', '?')
    print(f"  ${str(val):>12}  {t[1][:50]} | {t[2]} | {t[3]}")

conn.commit()
conn.close()

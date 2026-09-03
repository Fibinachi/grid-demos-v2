"""Step 1: Deduplicate corporation records and catalog unique diocese corps."""
import sqlite3
import re

DB = r'E:\grid\churches.db'
BACKUP = r'E:\grid\churches_merge_temp.db'

main_db = sqlite3.connect(DB)

# 1. What corporation records still exist in main DB?
cur = main_db.execute("SELECT name, COUNT(*) as c FROM churches WHERE name LIKE '%CORPORATION%' GROUP BY name ORDER BY c DESC")
existing = cur.fetchall()
print(f"=== Corp records still in main DB: {len(existing)} unique names ===")
total = sum(r[1] for r in existing)
print(f"Total rows: {total}")

# 2. What's in the backup that's NOT in main DB?
bdb = sqlite3.connect(BACKUP)
bcur = bdb.execute("SELECT name, COUNT(*) as c FROM churches WHERE name LIKE '%CORPORATION%' GROUP BY name ORDER BY c DESC")
backup = dict(bcur.fetchall())
bdb.close()

existing_names = {r[0] for r in existing}

print(f"\n=== Corp names in backup: {len(backup)} unique ===")
missing = {n: c for n, c in backup.items() if n not in existing_names}
print(f"Names NOT in main DB (need restoration): {len(missing)}")
for name, cnt in sorted(missing.items(), key=lambda x: -x[1])[:30]:
    print(f"  ×{cnt} | {name[:80]}")

# 3. For dupes still in main DB, show the worst offenders
dupes = [r for r in existing if r[1] > 1]
print(f"\n=== Duplicate names in main DB: {len(dupes)} ===")
for name, cnt in dupes[:20]:
    print(f"  ×{cnt} | {name[:80]}")

# 4. Count all RC diocese corps (from backup) that need dedup
corp_patterns = [
    '%ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%THE ROMAN CATHOLIC EPISCOPAL CORPORATION%',
    '%CATHOLIC EPISCOPAL CORPORATION%',
    '%EPISCOPAL CORPORATION OF%',
    '%EPISCOPAL CORPORATION FOR%',
    '%LA CORPORATION EPISCOPALE%',
    '%LA CORPORATION DE%',
]

print(f"\n=== RC Diocese corps summary (from backup) ===")
bdb = sqlite3.connect(BACKUP)
for pat in corp_patterns:
    cur = bdb.execute("SELECT COUNT(DISTINCT name) as uniq, COUNT(*) as total FROM churches WHERE name LIKE ?", (pat,))
    uniq, total = cur.fetchone()
    print(f"  {pat}: {uniq} unique names, {total} total rows")
bdb.close()

# 5. Show what cathedrals exist in main DB
print(f"\n=== Cathedrals in main DB ===")
cur = main_db.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%CATHEDRAL%'")
print(f"  Records with CATHEDRAL in name: {cur.fetchone()[0]}")
cur = main_db.execute("SELECT name, city, state, country, latitude, longitude FROM churches WHERE name LIKE '%CATHEDRAL%' AND latitude IS NOT NULL AND latitude != 0 LIMIT 20")
for r in cur.fetchall():
    lat = r[4] if r[4] else 0
    lon = r[5] if r[5] else 0
    print(f"  {r[0][:60]} | {r[1]}, {r[2]} {r[3]} | {lat:.4f}, {lon:.4f}")
    
# Show cathedrals in Canada specifically
print(f"\n=== Canadian Cathedrals ===")
cur = main_db.execute("SELECT name, city, state, latitude, longitude FROM churches WHERE name LIKE '%CATHEDRAL%' AND country = 'CA' AND latitude IS NOT NULL AND latitude != 0 LIMIT 30")
for r in cur.fetchall():
    print(f"  {r[0][:60]} | {r[1]}, {r[2]} | {r[3]:.4f}, {r[4]:.4f}")

main_db.close()

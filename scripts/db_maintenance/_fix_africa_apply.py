"""Comprehensive fix for data quality issues in/around Africa.

Fixes:
1. Buddhist entries with Thai/Vietnamese/CJK names at wrong coordinates → NULL lat/lng
2. Buddhist NULL-continent entries with bad coords → NULL lat/lng  
3. osm_import entries misclassified as Buddhist → correct faith
4. Jewish entries misclassified → correct faith
"""
import sqlite3, re

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

CHUNK = 500
fixes = []

# ============================================================
# CATEGORY 1: Buddhist entries mis-geocoded (wrong coordinates)
# These have Thai/Vietnamese/CJK script names placed at Africa coords
# Fix: NULL out lat/lng so they don't appear on maps
# ============================================================

buddhist_null_coords = [
    # Thai script (10 entries)
    973888,   # เขต อภ้ยทาน → CD
    1377011,  # วัดมงคลรัตน์ หลวงพ่อชื่น จังหวัดสุรินทร์ → MG
    1605584,  # วัดปากน้ำแหลมสิงห์ จันทบุรี → TD
    1606257,  # วัดบ้านธาตุใต้ อ แก่งคอย สระบุรี → CF
    1609999,  # วัดรางสะแกสูง - กลางทุ่ง → AO
    1655495,  # วัดวงศ์สง่าวันทาราม อำเภอบุ่งคล้า จังหวัดบึงกาฬ → CM
    1655566,  # วัดหลวงปู่คำบุนิมิตร อ.โขงเจียม จ.อุบลราชธานี → ZW
    1655894,  # วัดคีรีนาครัตนาราม จังหวัดลพบุรี → NG
    1768606,  # สถาบันพลังจิตตานุภาพสาขา193วัดคุณหญิงส้มจีน → CD
    2086746,  # ที่พักสงฆ์สวนป่าศรัทธาธรรม นครราชสีมา → TD
    # Vietnamese (2 entries)
    1517182,  # Chùa bà Thiên Hậu TP Mới Bình Dương → DZ
    1672026,  # Chùa Phước Ân → BW
    # CJK mis-geocoded (1 entry - 高野山真言宗 in CG)
    1804876,  # 高野山真言宗 総本山金剛峯寺 奥之院 → CG
    # NULL-continent bad coords (2 entries)
    2099756,  # วัดคลองพุทรา at (-0.154, 1.093) in Atlantic
    1295097,  # 台北市靈源寺濟公禪師解制壇 at (-1.593, -3.263) in Atlantic
]

for rid in buddhist_null_coords:
    fixes.append((rid, 'latitude', None))
    fixes.append((rid, 'longitude', None))
    # Also set continent to NULL since we're nuking coords
    c.execute("SELECT continent FROM churches WHERE rowid=?", (rid,))
    cont = c.fetchone()
    if cont and cont[0] == 'Africa':
        fixes.append((rid, 'continent', None))

# ============================================================
# CATEGORY 2: osm_import entries misclassified as Buddhist
# ============================================================

osm_faith_fixes = [
    (2340839, 'Christian'),   # Administration (denom=Russian Orthodox)
    (2894147, 'Christian'),   # Eglise Especo (Eglise = church in French)
    (2973397, 'Christian'),   # st. Sivlije (Christian saint name)
    (3028210, 'Sikh'),        # Sikh temple
    (3095873, 'Other'),       # Queen Victoria Nursery School (daycare)
    (3095944, 'Sikh'),        # Gurdiwara Siri Guru Singh Sab (Sikh gurdwara)
]

for rid, new_faith in osm_faith_fixes:
    fixes.append((rid, 'faith', new_faith))

# ============================================================
# CATEGORY 3: Jewish (blue) entries misclassified
# ============================================================

jewish_faith_fixes = [
    (1328337, 'Other'),       # Assemblée Provinciale du Kasaï-Orientale (govt building)
    (1375285, 'Christian'),   # Ack Church (Christian church)
    (2795710, 'Islam'),       # Mosque (clearly Islamic)
    (2844001, 'Christian'),   # Grand Seminaire (Catholic seminary)
    (1650123, 'Other'),       # CEWAC Camp Ground (camp ground, not religious)
    (1728339, 'Other'),       # Steinz Food & Beverages (food business)
    (1413302, 'Other'),       # Steinz Food & Beverages (duplicate)
    (1965587, 'Other'),       # CEWAC Camp Ground (duplicate)
    (2963882, 'Christian'),   # ufunuo na uzima (Swahili "Revelation and Life" - Christian)
]

for rid, new_faith in jewish_faith_fixes:
    fixes.append((rid, 'faith', new_faith))

# ============================================================
# EXECUTE
# ============================================================
print(f"Total individual field fixes: {len(fixes)}")

# Group by rowid and column for dedup
fix_set = set()
for rowid, col, val in fixes:
    fix_set.add((rowid, col, val))

deduped = list(fix_set)
print(f"After dedup: {len(deduped)} unique fixes")

# Apply in batches
applied = 0
for i in range(0, len(deduped), CHUNK):
    batch = deduped[i:i+CHUNK]
    batch_applied = 0
    for rowid, col, val in batch:
        if val is None:
            c.execute(f"UPDATE churches SET {col}=NULL WHERE rowid=?", (rowid,))
        else:
            c.execute(f"UPDATE churches SET {col}=? WHERE rowid=?", (val, rowid))
        batch_applied += c.rowcount
    conn.commit()
    applied += batch_applied
    print(f"  Batch {i//CHUNK + 1}: {batch_applied} rows affected")

print(f"\nTotal rows affected: {applied}")

# ============================================================
# VERIFY
# ============================================================
print("\n=== VERIFICATION ===")

# Count Buddhist in Africa still
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Buddhist' AND continent='Africa'")
print(f"Buddhist Africa remaining: {c.fetchone()[0]}")

# Count Jewish in Africa still
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND continent='Africa'")
print(f"Jewish Africa remaining: {c.fetchone()[0]}")

# Check fixed rowids still exist
print("\nFixed entries (should show updated values):")
for rid in buddhist_null_coords[:3] + [2340839, 2894147] + [1328337, 2795710]:
    c.execute("SELECT rowid, name, faith, latitude, longitude, continent FROM churches WHERE rowid=?", (rid,))
    r = c.fetchone()
    if r:
        nm = (r[1] or '')[:40]
        print(f"  rowid={rid}: {nm:40s} | faith={r[2]:12s} | lat={r[3]!s:10s} | lon={r[4]!s:10s} | cont={r[5]!s}")

# Check the specific Thai entries verify
print("\nThai entries (should all have NULL lat/lng):")
for rid in [973888, 1377011, 1605584, 1606257, 1609999, 1655495, 1655566, 1655894, 1768606, 2086746]:
    c.execute("SELECT rowid, name, latitude, longitude FROM churches WHERE rowid=?", (rid,))
    r = c.fetchone()
    nm = (r[1] or '')[:30]
    print(f"  rowid={rid}: {nm:30s} | lat={r[2]!s:10s} | lon={r[3]!s:10s}")

# Count Buddhist entries with NULL lat/lng in Africa (should be 12 = 10+1+1)
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Buddhist' AND continent='Africa' AND latitude IS NULL")
print(f"\nBuddhist Africa with NULL lat: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND continent='Africa' AND latitude IS NULL")
print(f"Jewish Africa with NULL lat: {c.fetchone()[0]}")

conn.close()
print("\nDone.")

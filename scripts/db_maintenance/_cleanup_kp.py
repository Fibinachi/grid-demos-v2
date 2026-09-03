"""
Clean up North Korea (KP) church records.
Uses rowid for operations since 'id' column is NULL on all KP rows.
"""
import sqlite3
from datetime import datetime, timezone

DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA busy_timeout=30000")
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

ts = datetime.now(timezone.utc).isoformat()
total_deleted = 0
total_enriched = 0

# 1. DELETE DUPLICATES (by holy_site_id)
duplicates_to_delete = [1134299, 1135089]  # Singyesa dup, Seongcheon dup
print("=== Removing duplicates ===")
for hs_id in duplicates_to_delete:
    c.execute("SELECT rowid, name, holy_site_id FROM churches WHERE country='KP' AND holy_site_id=?", (hs_id,))
    row = c.fetchone()
    if row:
        print(f"  Deleting: {row[1]} (rowid={row[0]}, holy_site_id={row[2]})")
        c.execute("DELETE FROM churches WHERE rowid=?", (row[0],))
        total_deleted += 1

# 2. DELETE KAILASAPPARA (mis-geocoded Hindu temple from Kerala)
print("\n=== Removing mis-geocoded Hindu temple ===")
c.execute("SELECT rowid, name, holy_site_id, latitude, longitude FROM churches WHERE country='KP' AND name LIKE '%Kailasappara%'")
for row in c.fetchall():
    print(f"  Deleting: {row[1]} (rowid={row[0]}, coords={row[3]},{row[4]})")
    c.execute("DELETE FROM churches WHERE rowid=?", (row[0],))
    total_deleted += 1

# 3. FIX Trinity
print("\n=== Fixing Trinity Church ===")
c.execute("SELECT rowid, name FROM churches WHERE country='KP' AND name LIKE '%Trinity%'")
trinity = c.fetchone()
if trinity:
    print(f"  '{trinity[1]}' -> 'Church of the Life-Giving Trinity'")
    c.execute("UPDATE churches SET name='Church of the Life-Giving Trinity', denomination='Eastern Orthodox', city='Pyongyang' WHERE rowid=?", (trinity[0],))
    total_enriched += 1

# 4. ENRICH Pyongyang
pyongyang = {
    "Ar-Rahman Mosque": ("Sunni Islam", "Pyongyang"),
    "Bongsu Church": ("Protestant", "Pyongyang"),
    "Changchung Cathedral": ("Roman Catholic", "Pyongyang"),
    "Chilgol Church": ("Protestant", "Pyongyang"),
    "Kwangbop Temple": ("Korean Buddhism", "Pyongyang"),
}
print("\n=== Enriching Pyongyang churches ===")
for name, (denom, city) in pyongyang.items():
    c.execute("SELECT rowid FROM churches WHERE country='KP' AND name=?", (name,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE churches SET city=?, denomination=? WHERE rowid=?", (city, denom, row[0]))
        total_enriched += 1
        print(f"  {name}: city={city}, denomination={denom}")

# 5. Tag Buddhist temples
buddhist = ["Gaesimsa", "Gwan-Eumsa", "Pohyonsa", "Pyohunsa",
            "Singyesa", "Woljeongsa Temple", "Yujomsa", "成佛寺", "靈通寺"]
print("\n=== Tagging Buddhist temples ===")
for name in buddhist:
    c.execute("SELECT rowid FROM churches WHERE country='KP' AND name=?", (name,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE churches SET denomination='Korean Buddhism', heritage_status='national_treasure' WHERE rowid=?", (row[0],))
        total_enriched += 1
        print(f"  {name}")

# 6. Flag suspicious
print("\n=== Flagging suspicious ===")
for name in ["Simbang-gogae", "대한예수교장로회 성천교회"]:
    c.execute("SELECT rowid FROM churches WHERE country='KP' AND name=?", (name,))
    row = c.fetchone()
    if row:
        c.execute("UPDATE churches SET confidence_score=0.3 WHERE rowid=?", (row[0],))
        print(f"  {name}: confidence->0.3")

# Log provenance
c.execute("""INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
    VALUES (?,?,?,?,?,?,?,?)""",
    ("manual", "cleanup_kp.py", ts, datetime.now(timezone.utc).isoformat(),
     total_deleted + total_enriched, "name,denomination,city,heritage_status,confidence_score",
     "completed",
     f"KP cleanup: {total_deleted} deleted (2 duplicates + 2 mis-geocoded), {total_enriched} enriched"))

conn.commit()

# Verify
c.execute("SELECT COUNT(*), faith FROM churches WHERE country='KP' GROUP BY faith ORDER BY COUNT(*) DESC")
print("\n=== Final KP Summary ===")
for cnt, faith in c.fetchall():
    print(f"  {faith}: {cnt}")
c.execute("SELECT COUNT(*) FROM churches WHERE country='KP'")
print(f"  TOTAL: {c.fetchone()[0]} (was 21, expected 17)")

# Show final list
print("\n=== Final KP Records ===")
c.execute("SELECT name, faith, denomination, city, heritage_status, confidence_score FROM churches WHERE country='KP' ORDER BY faith, name")
for row in c.fetchall():
    dn = str(row[2]) if row[2] else '-'
    ct = str(row[3]) if row[3] else '-'
    hs = str(row[4]) if row[4] else '-'
    cs = row[5] if row[5] else '-'
    print(f"  {row[0]:45s} | {row[1]:10s} | {dn:25s} | {ct:12s} | {hs:18s} | {cs}")

conn.close()
print("\nDone.")

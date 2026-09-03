"""
Fix Evangelical bucket (tax_id=333) — reclassify known denominations and fix bad traditions.
"""
import sqlite3, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"

db = sqlite3.connect(str(DB_PATH), timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.row_factory = sqlite3.Row

CHUNK = 500

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i+1)/elapsed
    eta = (total-i-1)/rate/60 if rate>0 else 0
    pct = (i+1)/total*100
    f = int(30*(i+1)/total)
    print(f"\r    {'█'*f}{'░'*(30-f)} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

print("=== EVANGELICAL BUCKET FIX ===\n")

fixes = []
total_affected = 0

# ============================================================
# PASS 1: Fix tradition='Catholic' → clear it (these are evangelical churches)
# ============================================================
print("Pass 1: Clearing incorrect tradition='Catholic' from Evangelical bucket...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND tradition='Catholic'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("UPDATE churches SET tradition=NULL WHERE id=?", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "clearing Catholic tradition")

n_catholic = len(rows)
print(f"\n  {n_catholic:,} tradition='Catholic' cleared → {n_catholic:,} remain Evangelical (correct)")
total_affected += n_catholic

# ============================================================
# PASS 2: Germany - Evangelische → Protestant/Lutheran
# ============================================================
print("\nPass 2: DE Evangelische → Protestant (tax_id=19)...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='DE' AND name LIKE '%Evangelische%'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("UPDATE churches SET taxonomy_id=19, tradition='Protestant' WHERE id=?", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "DE→Protestant")

print(f"\n  {len(rows):,} DE Evangelische → Protestant (tax_id=19)")

# Also: remaining DE in Evangelical that look like generic German churches
rows2 = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='DE'
      AND (name LIKE '%Kirche%' OR name LIKE '%Kapelle%' OR name LIKE '%Gemeinde%'
           OR name LIKE '%Dom%' OR name LIKE '%Münster%')
      AND name NOT LIKE '%Evangelische%'
""").fetchall()

for i in range(0, len(rows2), CHUNK):
    batch = rows2[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("UPDATE churches SET taxonomy_id=19, tradition='Protestant' WHERE id=?", ids)
    db.commit()

print(f"  {len(rows2):,} DE generic churches → Protestant (tax_id=19)")
total_affected += len(rows) + len(rows2)

# ============================================================
# PASS 3: Brazil - Assembleia de Deus → Pentecostal (id=746)
# ============================================================
print("\nPass 3: BR Assembleia de Deus → Pentecostal (id=746)...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='BR' 
      AND (name LIKE '%Assembleia de Deus%' OR name LIKE '%Assembléia de Deus%')
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=746, tradition='Pentecostal' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "AD→746")

print(f"\n  {len(rows):,} Assembleia de Deus → id=746 (Pentecostal)")
total_affected += len(rows)

# ============================================================
# PASS 4: Brazil + diaspora - Evangelho Quadrangular → id=743
# ============================================================
print("\nPass 4: Evangelho Quadrangular (Foursquare) → id=743...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND name LIKE '%Evangelho Quadrangular%'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=743, tradition='Pentecostal' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "Foursquare→743")

print(f"\n  {len(rows):,} Evangelho Quadrangular → id=743 (Pentecostal)")
total_affected += len(rows)

# ============================================================
# PASS 5: Brazil - Igreja Universal (IURD) → Neo-Pentecostal
# ============================================================
print("\nPass 5: Igreja Universal (IURD) → Pentecostal...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='BR' 
      AND (name LIKE '%Igreja Universal%' OR name LIKE '%IURD%')
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=218, tradition='Pentecostal' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "IURD→218")

print(f"\n  {len(rows):,} Igreja Universal → id=218 (Pentecostal)")
total_affected += len(rows)

# ============================================================
# PASS 6: US - Evangelical Free Church → id=335 (EFCA)
# ============================================================
print("\nPass 6: US Evangelical Free Church → id=335 (EFCA)...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='US' AND name LIKE '%Evangelical Free Church%'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=335, tradition='Evangelical Free Church' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "EFCA→335")

print(f"\n  {len(rows):,} Evangelical Free Church → id=335 (EFCA)")
total_affected += len(rows)

# ============================================================
# PASS 7: US - Evangelical Covenant → id=329
# ============================================================
print("\nPass 7: US Evangelical Covenant → id=329...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='US' AND name LIKE '%Evangelical Covenant%'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=329, tradition='Evangelical Covenant' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "Covenant→329")

print(f"\n  {len(rows):,} Evangelical Covenant → id=329")
total_affected += len(rows)

# ============================================================
# PASS 8: US - AME → id=367
# ============================================================
print("\nPass 8: AME churches → id=367...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND country='US' 
      AND (name LIKE '%AME %' OR name LIKE '%African Methodist Episcopal%')
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=367, tradition='Methodist' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "AME→367")

print(f"\n  {len(rows):,} AME → id=367 (Methodist)")
total_affected += len(rows)

# ============================================================
# PASS 9: NOT CHRISTIAN - Igreja Messianica Mundial
# ============================================================
print("\nPass 9: Igreja Messianica Mundial → NOT Christian...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 AND name LIKE '%Messi%nica Mundial%'
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=6, tradition='Japanese New Religion', faith='Other' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "Messianica→Other")

print(f"\n  {len(rows):,} Igreja Messianica → Other (NOT Christian)")
total_affected += len(rows)

# ============================================================
# PASS 10: LDS/Mormon misclassified
# ============================================================
print("\nPass 10: LDS/Mormon → LDS taxonomy...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 
      AND (name LIKE '%Latter-day%' OR name LIKE '%Mormon%' OR name LIKE '%LDS%')
""").fetchall()

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany("""UPDATE churches SET taxonomy_id=166, tradition='Latter-day Saints' WHERE id=?""", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "LDS→166")

print(f"\n  {len(rows):,} LDS/Mormon → LDS taxonomy (id=166)")
total_affected += len(rows)

# ============================================================
# PASS 11: Salvation Army → own taxonomy
# ============================================================
print("\nPass 11: Salvation Army → own taxonomy...")
t0 = time.time()
rows = db.execute("""
    SELECT id, name FROM churches 
    WHERE taxonomy_id=333 
      AND (name LIKE '%Salvation Army%' OR name LIKE '%Ejército de Salvación%' 
           OR name LIKE '%Armée du Salut%' OR name LIKE '%Ejercito de Salvacion%')
""").fetchall()

# Find Salvation Army taxonomy node
sa_node = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Salvation Army%' LIMIT 1").fetchone()
sa_id = sa_node['id'] if sa_node else 222  # fallback

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    ids = [(r['id'],) for r in batch]
    db.executemany(f"UPDATE churches SET taxonomy_id={sa_id}, tradition='Holiness' WHERE id=?", ids)
    db.commit()
    progress_bar(i+len(batch), len(rows), t0, "SA→own")

print(f"\n  {len(rows):,} Salvation Army → id={sa_id}")
total_affected += len(rows)

# ============================================================
# PASS 12: Fix tradition for remaining — clear bad traditions that conflict
# ============================================================
print("\nPass 12: Clearing conflicting traditions from Evangelical bucket...")
bad_traditions = [
    'Anglican', 'Orthodox', 'Eastern Orthodox', 'Catholic', 'Catholic Churches',
    'Rabbinic', "Jehovah's Witnesses", 'Lutheran', 'Methodist', 'Presbyterian',
    'Holiness Churches', 'Reform', 'Restorationist'
]
t0 = time.time()
for trad in bad_traditions:
    rows = db.execute("""
        SELECT id FROM churches WHERE taxonomy_id=333 AND tradition=?
    """, (trad,)).fetchall()
    if not rows:
        continue
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i+CHUNK]
        ids = [(r['id'],) for r in batch]
        db.executemany("UPDATE churches SET tradition=NULL WHERE id=?", ids)
        db.commit()
    print(f"  {len(rows):>6,}  tradition='{trad}' → NULL")
    total_affected += len(rows)

# ============================================================
# FINAL: Summary
# ============================================================
remaining = db.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=333").fetchone()[0]
print(f"\n{'='*60}")
print(f"TOTAL AFFECTED: {total_affected:,} records across 12 passes")
print(f"Remaining in Evangelical bucket: {remaining:,}")
print(f"{'='*60}")

# Show what's left by country
print("\n--- REMAINING BY COUNTRY (top 10) ---")
for r in db.execute("""
    SELECT country, COUNT(*) n FROM churches WHERE taxonomy_id=333
    GROUP BY country ORDER BY n DESC LIMIT 10
""").fetchall():
    print(f"  {r['country'] or 'NULL':6s}  {r['n']:>8,}")

db.close()
print("\nDone.")

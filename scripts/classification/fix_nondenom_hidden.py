"""
Fix hidden denominations in Non-Denom bucket (tax_id=388).
Moves clearly misclassified churches to their proper taxonomy nodes.
"""
import sqlite3, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
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

def apply_fix(label, rows, tax_id, tradition, extra_sets=None):
    """Apply taxonomy fix to a batch of rows."""
    if not rows:
        print(f"  {label}: 0 records — skipped")
        return 0
    t0 = time.time()
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i+CHUNK]
        ids = [(r['id'],) for r in batch]
        db.executemany(f"UPDATE churches SET taxonomy_id=?, tradition=? WHERE id=?", 
                       [(tax_id, tradition, r['id']) for r in batch])
        db.commit()
        progress_bar(i+len(batch), len(rows), t0, label)
    n = len(rows)
    print(f"\n  {label}: {n:,} → tax_id={tax_id}, tradition='{tradition}'")
    if extra_sets:
        for set_label, set_rows, set_tax, set_trad in extra_sets:
            if set_rows:
                apply_fix(f"  └ {set_label}", set_rows, set_tax, set_trad)
    return n

print("=== NON-DENOM HIDDEN DENOMINATION FIX ===\n")
total = 0

# ============================================================
# PASS 1: Foursquare / Quadrangular → id=403 (Foursquare Church)
# ============================================================
print("Pass 1: Foursquare/Quadrangular → Foursquare Church (id=403)")
rows = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND (name LIKE '%Foursquare%' OR name LIKE '%Quadrangular%')
    AND name NOT LIKE '%Igreja Quadrangular%'
""").fetchall()
total += apply_fix("Foursquare", rows, 403, "Pentecostal")

# Igreja do Evangelho Quadrangular (Brazil)
rows_br = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND name LIKE '%Igreja%Quadrangular%'
""").fetchall()
total += apply_fix("  └ BR Igreja Quadrangular", rows_br, 403, "Pentecostal")

# ============================================================
# PASS 2: Calvary Chapel → id=130
# ============================================================
print("\nPass 2: Calvary Chapel → id=130")
rows = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND name LIKE '%Calvary Chapel%'
""").fetchall()
total += apply_fix("Calvary Chapel", rows, 130, "Calvary Chapel")

# ============================================================
# PASS 3: Unitarian Universalist → id=160
# ============================================================
print("\nPass 3: Unitarian Universalist → id=160")
rows = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND (name LIKE '%Unitarian%' OR name LIKE '%Universalist%')
""").fetchall()
total += apply_fix("Unitarian/Universalist", rows, 160, "Unitarian Universalist")

# ============================================================
# PASS 4: Assemblies of God → id=392
# ============================================================
print("\nPass 4: Assemblies of God → id=392")
rows = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND (name LIKE '%Assemblies of God%' OR name LIKE '%Assemblies Of God%'
         OR name LIKE '%Assembly of God%')
""").fetchall()
total += apply_fix("Assemblies of God", rows, 392, "Pentecostal")

# ============================================================
# PASS 5: Church of the Nazarene → id=? (find node)
# ============================================================
print("\nPass 5: Church of the Nazarene")
naz = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Nazarene%' AND name NOT LIKE '%Apostolic%' LIMIT 1").fetchone()
if naz:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Church of the Nazarene%'
    """).fetchall()
    total += apply_fix("Church of the Nazarene", rows, naz['id'], "Wesleyan")

# ============================================================
# PASS 6: Seventh-day Adventist → find node
# ============================================================
print("\nPass 6: Seventh-day Adventist")
sda = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Seventh%Adventist%' LIMIT 1").fetchone()
if sda:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND (name LIKE '%Seventh-day%' OR name LIKE '%Seventh Day%')
    """).fetchall()
    total += apply_fix("Seventh-day Adventist", rows, sda['id'], "Adventist")

# ============================================================
# PASS 7: Church of God (Cleveland) — careful: COGIC is Pentecostal
# ============================================================
print("\nPass 7: Church of God (discern subtype)")
# Church of God in Christ → id=397 (Pentecostal)
rows_cogic = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND name LIKE '%Church of God in Christ%'
""").fetchall()
total += apply_fix("  COGIC → Pentecostal", rows_cogic, 397, "Pentecostal")

# Church of God of Prophecy → id=398
rows_cogop = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND name LIKE '%Church of God of Prophecy%'
""").fetchall()
total += apply_fix("  COGOP → id=398", rows_cogop, 398, "Pentecostal")

# Generic "Church of God" — use id=137 (generic Church of God)
rows_cog = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND name LIKE '%Church of God%'
    AND name NOT LIKE '%Church of God in Christ%'
    AND name NOT LIKE '%Church of God of Prophecy%'
""").fetchall()
total += apply_fix("  Generic Church of God → id=137", rows_cog, 137, "Pentecostal")

# ============================================================
# PASS 8: Free Methodist → find node
# ============================================================
print("\nPass 8: Free Methodist")
fm = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Free Methodist%' LIMIT 1").fetchone()
if fm:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Free Methodist%'
    """).fetchall()
    total += apply_fix("Free Methodist", rows, fm['id'], "Methodist")

# ============================================================
# PASS 9: Wesleyan → find node
# ============================================================
print("\nPass 9: Wesleyan")
wes = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Wesleyan Church%' OR name='Wesleyan' LIMIT 1").fetchone()
if wes:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Wesleyan%' AND name NOT LIKE '%Free Methodist%'
    """).fetchall()
    total += apply_fix("Wesleyan", rows, wes['id'], "Wesleyan")

# ============================================================
# PASS 10: Real Church of Christ (a cappella) 
# pattern: ends with "Church of Christ" or starts with "[City] Church of Christ"
# ============================================================
print("\nPass 10: Real Church of Christ (a cappella, not 'Christian Fellowship')")
coc = db.execute("SELECT id FROM taxonomy WHERE name='Church of Christ' LIMIT 1").fetchone()
if coc:
    # Exact suffix "Church of Christ" (not "Church of Christian ...")
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND (name LIKE '% Church of Christ' OR name='Church of Christ')
        AND name NOT LIKE '%United Church of Christ%'
        AND name NOT LIKE '%Church of Christian%'
    """).fetchall()
    total += apply_fix("Church of Christ (a cappella)", rows, coc['id'], "Restorationist")

# ============================================================
# PASS 11: Vineyard → id=126 or 163
# ============================================================
print("\nPass 11: Vineyard")
vy = db.execute("SELECT id FROM taxonomy WHERE name='Association of Vineyard Churches' LIMIT 1").fetchone()
if vy:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Vineyard%' AND name NOT LIKE '%Vineyard Church%'
    """).fetchall()
    total += apply_fix("Vineyard", rows, vy['id'], "Neo-charismatic")

# ============================================================
# PASS 12: Christian & Missionary Alliance
# ============================================================
print("\nPass 12: Christian & Missionary Alliance")
cma = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Christian%Missionary%Alliance%' LIMIT 1").fetchone()
if cma:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND (name LIKE '%Christian & Missionary%' OR name LIKE '%Christian and Missionary%'
             OR name LIKE '%C&MA%')
    """).fetchall()
    total += apply_fix("Christian & Missionary Alliance", rows, cma['id'], "Evangelical")

# ============================================================
# PASS 13: Congregational → find node
# ============================================================
print("\nPass 13: Congregational")
cong = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Congregational%' AND id < 200 LIMIT 1").fetchone()
if cong:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Congregational Church%' OR name LIKE '%Congregational Christian%'
    """).fetchall()
    total += apply_fix("Congregational", rows, cong['id'], "Congregational")

# ============================================================
# PASS 14: Disciples of Christ
# ============================================================
print("\nPass 14: Disciples of Christ")
doc = db.execute("SELECT id FROM taxonomy WHERE name LIKE '%Disciples of Christ%' LIMIT 1").fetchone()
if doc:
    rows = db.execute("""
        SELECT id, name FROM churches WHERE taxonomy_id=388 
        AND name LIKE '%Disciples of Christ%'
    """).fetchall()
    total += apply_fix("Disciples of Christ", rows, doc['id'], "Restorationist")

# ============================================================
# PASS 15: Mormon/LDS → id=166
# ============================================================
print("\nPass 15: LDS/Mormon")
rows = db.execute("""
    SELECT id, name FROM churches WHERE taxonomy_id=388 
    AND (name LIKE '%Mormon%')
""").fetchall()
total += apply_fix("Mormon/LDS", rows, 166, "Latter-day Saints")

# ============================================================
# PASS 16: Non-Christian faiths that slipped in
# ============================================================
print("\nPass 16: Non-Christian faiths → Other")
other_faiths = [
    ("%Islam%", "Islam", 4),
    ("%Mosque%", "Islam", 4),
    ("%Masjid%", "Islam", 4),
    ("%Buddhist%", "Buddhist", 3),
    ("%Hindu%", "Hindu", 3),
    ("%Sikh%", "Sikh", 5),
    ("%Gurdwara%", "Sikh", 5),
    ("%Jewish%", "Jewish", 7),
    ("%Synagogue%", "Jewish", 7),
]
for pattern, faith, tax_id in other_faiths:
    rows = db.execute(
        "SELECT id, name FROM churches WHERE taxonomy_id=388 AND name LIKE ?",
        (pattern,)
    ).fetchall()
    total += apply_fix(f"  {faith}", rows, tax_id, faith)

# ============================================================
# FINAL: Summary
# ============================================================
remaining = db.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=388").fetchone()[0]
print(f"\n{'='*60}")
print(f"TOTAL MOVED: {total:,} records")
print(f"Remaining in Non-Denom: {remaining:,}")
print(f"{'='*60}")

db.close()
print("\nDone.")

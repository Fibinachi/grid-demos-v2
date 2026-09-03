"""
Normalize Anglican church names:
1. Expand St. -> Saint (Street vs Saint disambiguation)
2. Drop trailing ' Church' (not 'Church of')
Processes all entries in anglican_hierarchy + all Anglican-tagged entries.
"""
import sqlite3, re, sys

DB = "churches.db"
CHUNK_SIZE = 500
LOG_SOURCE = "anglican_name_normalize_2026-07-03"

STREET_KEYWORDS = {"main", "broad", "high", "market", "church", "park",
                   "oak", "elm", "maple", "pine", "cedar", "walnut",
                   "chestnut", "washington", "lincoln", "jefferson",
                   "madison", "monroe", "state", "water", "front",
                   "river", "lake", "hill", "king", "queen"}

def normalize_name(name):
    """Normalize a church name: expand St->Saint, drop trailing Church."""
    if not name:
        return None
    original = name
    n = name.strip()
    
    def expand_st(m):
        before = n[max(0, m.start()-20):m.start()].strip()
        last_word = before.split()[-1].lower() if before.split() else ""
        if re.search(r'\d', last_word):
            return "Street"
        if last_word in STREET_KEYWORDS:
            return "Street"
        return "Saint"
    
    n = re.sub(r'(?<!\w)(St)\.?(?=\s+[A-Z])', expand_st, n, flags=re.IGNORECASE)
    n = re.sub(r'(?<!\w)(St)\.?$', expand_st, n, flags=re.IGNORECASE)
    n = re.sub(r'\s+Church\s*$', '', n, flags=re.IGNORECASE)
    
    if n != original:
        return n
    return None

db = sqlite3.connect(DB, timeout=30)

# Get all Anglican entries that need normalization
entries = db.execute("""
    SELECT DISTINCT c.id, c.name
    FROM anglican_hierarchy ah
    JOIN churches c ON ah.church_id = c.id
    WHERE c.name IS NOT NULL AND c.name != ''
    ORDER BY c.id
""").fetchall()

print(f"Total Anglican entries: {len(entries):,}")

total_changed = 0
total_skipped = 0
changes = []

for row in entries:
    cid, name = row
    normalized = normalize_name(name)
    if normalized:
        changes.append((normalized, cid))
        total_changed += 1

print(f"Names to normalize: {total_changed:,}")
print(f"Skipped (unchanged): {len(entries) - total_changed:,}")

# Apply in chunks with progress bar
if total_changed > 0:
    print()
    for i in range(0, len(changes), CHUNK_SIZE):
        batch = changes[i:i+CHUNK_SIZE]
        for new_name, cid in batch:
            # Get old name
            old = db.execute("SELECT name FROM churches WHERE id=?", (cid,)).fetchone()[0]
            db.execute("UPDATE churches SET name=? WHERE id=?", (new_name, cid))
            db.execute("""
                INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                VALUES (?, 'name', ?, ?, ?)
            """, (cid, old, new_name, LOG_SOURCE))
        db.commit()
        
        pct = min(i + CHUNK_SIZE, total_changed) / total_changed * 100
        bar_len = 40
        filled = int(bar_len * (i + CHUNK_SIZE) / total_changed)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"  [{bar}] {min(i+CHUNK_SIZE, total_changed):,}/{total_changed:,} ({pct:.0f}%)", end="\r")
    print()

print()
print(f"Done. {total_changed:,} names normalized.")

# Sample results
print()
print("=== Sample normalizations ===")
samples = db.execute("""
    SELECT id, name FROM churches WHERE id IN (
        SELECT church_id FROM enrichment_change_log 
        WHERE change_source=? AND field_name='name'
        LIMIT 10
    )
""", (LOG_SOURCE,)).fetchall()
for s in samples:
    print(f"  ID={s[0]}: {s[1]}")

db.close()

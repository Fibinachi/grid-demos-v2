#!/usr/bin/env python3
"""
_clean_islam_suffixes_v2.py — Strip corporate suffixes from Islam names.

Loads all Islam names into memory, strips via Python string ops, batch-writes.
"""
import sqlite3, time, shutil

DB = r'E:\grid\churches.db'

# Suffixes to strip (longer first for unambiguous matching)
SUFFIXES = sorted(['INCORPORATED', 'CORPORATION', 'INTERNATIONAL', 'ENTERPRISES', 
                   'ORGANIZATION', 'ASSOCIATION', 'FELLOWSHIP',
                   'LIMITED', 'COMPANY', 'SERVICES', 'SOCIETY',
                   'ENTERPRISE', 'SERVICE', 'GROUP',
                   'GLOBAL', 'WORLDWIDE',
                   'INC', 'LLC', 'LTD', 'CORP', 'ASSOC'], key=len, reverse=True)

def progress_bar(current, total, start_time, extra=""):
    """Draw a progress bar with ETA."""
    cols = shutil.get_terminal_size().columns - 20
    bar_w = max(10, cols - 40)
    pct = current / total if total else 0
    filled = int(bar_w * pct)
    bar = '█' * filled + '░' * (bar_w - filled)
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 and current > 0 else 0
    if rate > 0 and current < total:
        eta = (total - current) / rate
        eta_str = f"{eta:.0f}s"
    else:
        eta_str = "done!"
    print(f"\r  {current:>7,}/{total:<7,} [{bar}] {pct:>5.1f}% | {rate:>,.0f} rec/s | ETA {eta_str} {extra}", end='', flush=True)

conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

t0 = time.time()

# Load all Islam entries with names
c.execute("""
    SELECT id, COALESCE(NULLIF(TRIM(name_transliterated), ''), name)
    FROM churches
    WHERE faith='Islam' AND name IS NOT NULL AND name != ''
""")
rows = c.fetchall()
total = len(rows)
print(f"Loaded {total:,} Islam records in {time.time()-t0:.1f}s", flush=True)

# Process in memory
updates = []
stripped_count = 0
CHUNK = 50000
t1 = time.time()

progress_bar(0, total, t1, "starting...")

for i, (rid, name) in enumerate(rows):
    original = name.rstrip(' .,;:#')
    new_name = original
    
    # Try each suffix
    for suffix in SUFFIXES:
        # Check if name ends with " SUFFIX" (case-insensitive)
        expected_len = len(suffix) + 1  # space + suffix
        if len(new_name) > expected_len and new_name[-expected_len:].upper() == ' ' + suffix:
            new_name = new_name[:-expected_len].rstrip(' .,;:#')
            break
        # Check with period: " SUFFIX."
        expected_len_dot = len(suffix) + 2
        if len(new_name) > expected_len_dot and new_name[-expected_len_dot:].upper() == ' ' + suffix + '.':
            new_name = new_name[:-expected_len_dot].rstrip(' .,;:#')
            break
    
    if new_name != original:
        updates.append((new_name, rid))
        stripped_count += 1
    
    if len(updates) >= CHUNK:
        c.executemany("UPDATE churches SET name_transliterated = ? WHERE id = ?", updates)
        conn.commit()
        progress_bar(i + 1, total, t1, f"| {stripped_count:,} stripped")
        updates = []

if updates:
    c.executemany("UPDATE churches SET name_transliterated = ? WHERE id = ?", updates)
    conn.commit()

progress_bar(total, total, t1, f"| {stripped_count:,} stripped")
print()

elapsed = time.time() - t0
print(f"\nDone in {elapsed:.1f}s")
print(f"Total records processed: {len(rows):,}")
print(f"Records stripped: {stripped_count:,}")

# Verify
c.execute("""
    SELECT name, name_transliterated FROM churches 
    WHERE faith='Islam' AND name_transliterated != name 
    LIMIT 15
""")
for name, translit in c.fetchall():
    print(f"  '{name[:60]}' → '{translit[:60]}'")

conn.close()

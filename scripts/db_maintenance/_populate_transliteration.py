"""Populate name_transliterated using rowid-cursor batch iteration (3.4M recs, non-unique IDs)."""
import sqlite3, time
from datetime import datetime
from anyascii import anyascii

DB = 'E:/grid/churches.db'
SCRIPT_NAME = '_populate_transliteration.py'

conn = sqlite3.connect(DB)
c = conn.cursor()

# Count total names
c.execute("SELECT COUNT(*) FROM churches WHERE name IS NOT NULL AND name != ''")
total_names = c.fetchone()[0]
print(f'Total records with names: {total_names:,}')

# Count already transliterated
c.execute("SELECT COUNT(*) FROM churches WHERE name_transliterated IS NOT NULL AND name_transliterated != ''")
already = c.fetchone()[0]
print(f'Already transliterated: {already:,}')

BATCH = 10000
start_time = time.time()
updated = 0
scanned = 0
last_rowid = 0

while scanned < total_names:
    c.execute(
        "SELECT rowid, id, name FROM churches WHERE name IS NOT NULL AND name != '' AND rowid > ? ORDER BY rowid LIMIT ?",
        (last_rowid, BATCH)
    )
    rows = c.fetchall()
    if not rows:
        break

    updates = []
    for rowid, rid, name in rows:
        trans = anyascii(name)
        if trans != name and trans.strip():
            updates.append((trans, rowid))

    if updates:
        c.executemany(
            "UPDATE churches SET name_transliterated = ? WHERE rowid = ?",
            updates
        )
        conn.commit()
        updated += len(updates)

    scanned += len(rows)
    last_rowid = rows[-1][0]  # track last rowid for next cursor

    if scanned % 100000 == 0 or scanned >= total_names:
        elapsed = time.time() - start_time
        rate = scanned / elapsed if elapsed > 0 else 0
        pct = 100 * scanned / total_names
        print(f'  scanned {scanned:>8,}/{total_names:,} ({pct:.1f}%) | updated {updated:>8,} | {rate:.0f} rec/s | {elapsed:.0f}s')

elapsed = time.time() - start_time
print(f'\nComplete: {updated:,} transliterations from {scanned:,} names scanned in {elapsed:.1f}s')

# Log provenance
c.execute(
    "INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_inserted, churches_updated, "
    "fields_populated, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    ('anyascii', SCRIPT_NAME, datetime.now().isoformat(), datetime.now().isoformat(), 0, updated,
     'name_transliterated', total_names, updated, 'completed',
     f'Transliterated {updated} non-ASCII names using anyascii library')
)
conn.commit()
conn.close()
print('Provenance logged.')

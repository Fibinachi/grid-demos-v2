"""Clean up round 3: article/blog titles and fix garbled names."""
import sqlite3
from datetime import datetime

SCRIPT_NAME = '_cleanup_round3_artifacts.py'
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

now = datetime.now().isoformat()

# === ARTICLES TO DELETE ===
article_ids = [296329, 296474, 296782, 343746, 343810, 343850]

# Verify they're all still there
c.execute(f"SELECT id, name FROM churches WHERE id IN ({','.join(map(str, article_ids))})")
still_there = c.fetchall()
print(f'Records to delete: {len(still_there)}')
for r in still_there:
    print(f'  id={r[0]} {r[1][:70]}')

# Delete from child tables first
tables = [
    'church_broadcast', 'church_classification_meta', 'church_contacts',
    'church_enrichment', 'church_operations'
]
for tid in article_ids:
    for tbl in tables:
        c.execute(f"DELETE FROM {tbl} WHERE church_id=?", (tid,))
    # Log enrichment change
    c.execute("""
        INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at)
        VALUES (?, 'entire_record', 'article/blog artifact', NULL, 'manual_cleanup', ?)
    """, (tid, now))
    # Delete from churches
    c.execute("DELETE FROM churches WHERE id=?", (tid,))

db.commit()

# Log batch provenance
c.execute(
    "INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_inserted, churches_updated, "
    "fields_populated, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    ('manual_cleanup', SCRIPT_NAME, now, datetime.now().isoformat(), 0, 0,
     '', len(article_ids), 0, 'completed', f'Deleted {len(article_ids)} article/blog artifacts from multiple sources')
)
db.commit()
print(f'\nDeleted {len(article_ids)} article/blog artifact records')

# === FIX KINGSTON VILLAGE BAPTIST NAME ===
c.execute("SELECT id, name FROM churches WHERE id=293059")
r = c.fetchone()
if r:
    old_name = r[1]
    new_name = old_name.replace('\xa0', ' ')
    c.execute("UPDATE churches SET name=? WHERE id=?", (new_name, r[0]))
    c.execute("""
        INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at)
        VALUES (?, 'name', ?, ?, 'manual_cleanup', ?)
    """, (r[0], old_name, new_name, now))
    db.commit()
    print(f'\nFixed Kingston Village Baptist:')
    print(f'  Old: {repr(old_name)}')
    print(f'  New: {repr(new_name)}')
else:
    print('\nKingston Village Baptist already fixed or deleted')

db.close()
print('\nDone. Round 3 cleanup complete.')

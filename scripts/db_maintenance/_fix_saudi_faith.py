"""Fix misclassified faiths in Saudi Arabia. All non-Islamic entries are set to NULL (unknown)."""
import sqlite3

DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# Get all non-Islamic entries in Saudi Arabia
c.execute("SELECT id, faith, name, source FROM churches WHERE country='SA' AND faith!='Islam'")
rows = c.fetchall()

print(f'Total non-Islamic entries to fix: {len(rows)}')

for row in rows:
    cid, old_faith, name, source = row
    if cid is None:
        print(f'Skipping row with NULL id: {row}')
        continue
    # Update faith to NULL
    c.execute("UPDATE churches SET faith=NULL WHERE id=?", (cid,))
    
    # Log the change
    c.execute(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, enrichment_version, changed_at) VALUES (?,?,?,?,?,?,datetime('now'))",
        (cid, 'faith', old_faith, None, 'auto_fix_saudi_faith', 1)
    )

conn.commit()
conn.close()
print('Done.')
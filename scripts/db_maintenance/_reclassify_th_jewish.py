"""Reclassify mis‑tagged Thai Jewish entries – they are actually Buddhist/Hindu."""
import sqlite3, json, os, sys

DB = 'E:/grid/churches.db'

# Helper to classify faith from name
def classify_faith(name):
    low = name.lower()
    if 'วัด' in low or 'temple' in low or 'pagoda' in low or 'stupa' in low:
        return 'Buddhist'
    if 'iskcon' in low or 'hindu' in low or 'shiva' in low or 'ganesha' in low or 'devi' in low:
        return 'Hindu'
    # fallback – treat as Buddhist (most are temples)
    return 'Buddhist'

conn = sqlite3.connect(DB)
c = conn.cursor()

# Find all Thai Jewish entries from holy_sites_import
c.execute("""
    SELECT id, name, faith, denomination_affiliation
    FROM churches
    WHERE country='TH' AND source='holy_sites_import' AND faith='Jewish'
""")
rows = c.fetchall()

print(f'Found {len(rows)} Thai Jewish entries to reclassify.')

updates = []
log_entries = []

for row in rows:
    church_id, name, old_faith, denom = row
    new_faith = classify_faith(name)
    if new_faith != old_faith:
        updates.append((new_faith, church_id))
        log_entries.append({
            'church_id': church_id,
            'field_name': 'faith',
            'old_value': old_faith,
            'new_value': new_faith,
            'change_source': 'manual_reclassify_th_jewish'
        })
        print(f'{church_id:6d} “{name}” → {new_faith}')

# Apply updates
for new_faith, church_id in updates:
    c.execute('UPDATE churches SET faith=? WHERE id=?', (new_faith, church_id))

# Log to enrichment_change_log (field_name, old_value, new_value)
if log_entries:
    c.executemany(
        'INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, changed_at) '
        'VALUES (:church_id, :field_name, :old_value, :new_value, :change_source, datetime("now"))',
        log_entries
    )
    print(f'Logged {len(log_entries)} provenance entries to enrichment_change_log.')

conn.commit()
conn.close()
print('Done.')
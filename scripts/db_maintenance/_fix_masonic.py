"""
Fix Masonic Temple entries: set faith=Other, faith_tradition=Masonic
for any entry with 'Masonic' in the name that isn't already tagged correctly.

Uses rowid for matching since id=NULL for holy_sites_import rows.
"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

# Find all Masonic entries not yet tagged as Other/Masonic
c.execute("""
    SELECT rowid, id, name, faith, faith_tradition, country, city, source
    FROM churches
    WHERE name LIKE '%masonic%'
      AND (faith IS NULL OR faith != 'Other' OR faith_tradition IS NULL OR faith_tradition != 'Masonic')
    ORDER BY country, name
""")
rows = c.fetchall()

print(f"Found {len(rows)} Masonic entries to fix\n")

# Preview
for r in rows:
    rid = str(r[1] or '(no id)')
    print(f"  rowid={r[0]:>8} | id={rid:12s} | faith={str(r[3] or '-'):12s} | trait={str(r[4] or '-'):15s} | {str(r[2] or '')[:70]:70s} | {r[5] or '-'} | {str(r[6] or '-'):20s} | src={r[7] or '-'}")

# Auto-apply (user confirmed via chat)
print(f"\n{len(rows)} entries will be set to: faith=Other, faith_tradition=Masonic")
print("Auto-applying...")

# Apply fixes
fixed = 0
for r in rows:
    old_faith = r[3]
    old_trait = r[4]
    c.execute("""
        UPDATE churches
        SET faith = 'Other', faith_tradition = 'Masonic'
        WHERE rowid = ?
    """, (r[0],))
    fixed += 1

conn.commit()

# Log provenance
from datetime import datetime
ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
for r in rows:
    c.execute("""
        INSERT INTO provenance_log (church_id, source, action, timestamp, details)
        VALUES (?, ?, 'updated', ?, ?)
    """, (
        r[1] or None,
        'masonic_fix_script',
        ts,
        f'faith: {r[3] or "NULL"}->Other, faith_tradition: {r[4] or "NULL"}->Masonic'
    ))
conn.commit()

print(f"\n✓ Fixed {fixed} entries")
print(f"✓ Logged {fixed} provenance entries")

# Verify
c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE name LIKE '%masonic%'
      AND (faith IS NULL OR faith != 'Other' OR faith_tradition IS NULL OR faith_tradition != 'Masonic')
""")
remaining = c.fetchone()[0]
print(f"✓ Remaining unfixed: {remaining}")

conn.close()

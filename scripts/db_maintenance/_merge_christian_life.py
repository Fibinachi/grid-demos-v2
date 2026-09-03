"""
Merge #539438 (Christian Life Church, formerly CHITTY J STEPHEN REV) into #656887 (CHRISTIAN LIFE CHURCH).
Same address (2700 Bush River Rd, Columbia SC). Keep #656887, delete #539438.
"""

import sys
sys.path.insert(0, 'E:/grid')
from gw_db import connect, Provenance, log_change
from datetime import datetime

KEEP = 656887
MERGE = 539438
SOURCE = "manual_merge"
SCRIPT = "_merge_christian_life.py"
NOW = datetime.now().isoformat()

db = connect()
cur = db.cursor()

print("=== Step 1: Update keeper record #656887 ===")
with Provenance(db, SCRIPT, source=SOURCE, action="updated",
                fields="denomination,taxonomy_id"):
    cur.execute("""
        UPDATE churches 
        SET denomination = 'Assemblies of God',
            taxonomy_id = 392
        WHERE id = ?
    """, (KEEP,))
    print(f"  Updated: {cur.rowcount}")

print("\n=== Step 2: Transfer church_enrichment (has diocese/province data) ===")
with Provenance(db, SCRIPT, source=SOURCE, action="merged",
                fields="church_enrichment"):
    # #656887 has an empty enrichment row - delete it
    cur.execute("DELETE FROM church_enrichment WHERE church_id = ?", (KEEP,))
    print(f"  Deleted empty enrichment for #{KEEP}: {cur.rowcount}")
    # Reassign #539438's enrichment to #656887
    cur.execute("UPDATE church_enrichment SET church_id = ? WHERE church_id = ?", (KEEP, MERGE))
    print(f"  Transferred enrichment: {cur.rowcount}")

print("\n=== Step 3: Transfer church_staff (Pastor J. Stephen Chitty) ===")
with Provenance(db, SCRIPT, source=SOURCE, action="merged",
                fields="church_staff"):
    cur.execute("UPDATE church_staff SET church_id = ? WHERE church_id = ?", (KEEP, MERGE))
    print(f"  Transferred staff: {cur.rowcount}")

print("\n=== Step 4: Fix website contacts ===")
with Provenance(db, SCRIPT, source=SOURCE, action="merged",
                fields="church_contact_values"):
    # Delete wrong website on #656887
    cur.execute("DELETE FROM church_contact_values WHERE church_id = ? AND value LIKE '%dioezese-linz%'", (KEEP,))
    print(f"  Deleted wrong website on #{KEEP}: {cur.rowcount}")
    # Reassign #539438's correct website to #656887
    cur.execute("UPDATE church_contact_values SET church_id = ? WHERE church_id = ?", (KEEP, MERGE))
    print(f"  Transferred contacts: {cur.rowcount}")

print("\n=== Step 5: Delete duplicate rows (identical data) ===")
with Provenance(db, SCRIPT, source=SOURCE, action="merged",
                fields="church_territories,church_classification_meta,church_broadband,church_sources"):
    for tname in ['church_territories', 'church_classification_meta', 'church_broadband', 'church_sources']:
        cur.execute(f"DELETE FROM {tname} WHERE church_id = ?", (MERGE,))
        print(f"  Deleted {tname} for #{MERGE}: {cur.rowcount}")

print("\n=== Step 6: Delete merged record #539438 ===")
with Provenance(db, SCRIPT, source=SOURCE, action="deleted",
                fields="churches"):
    cur.execute("DELETE FROM churches WHERE id = ?", (MERGE,))
    print(f"  Deleted church #{MERGE}: {cur.rowcount}")

print("\n=== Step 7: Update enrichment_change_log ===")
log_change(db, church_id=KEEP, field_name="merged_from",
           old_value=None,
           new_value=f"Merged #{MERGE} (formerly CHITTY J STEPHEN REV, renamed Christian Life Church) into #{KEEP}. "
                     f"Transferred: enrichment, staff (J. Stephen Chitty), website (clcolumbia.com). "
                     f"Deleted #{MERGE}.",
           source=SOURCE)

db.commit()
print("\n✅ Merge complete! #656887 now has all data from #539438.")
db.close()

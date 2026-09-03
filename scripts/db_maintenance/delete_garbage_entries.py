"""
Delete garbage church entries: no city, no GPS, no address, and names that are
clearly non-church records (administrative, spam, functional descriptions, etc.)
Also deletes csv_import entries that are triple-empty (botched bulk import).

Usage:
  python scripts/db_maintenance/delete_garbage_entries.py --dry-run
  python scripts/db_maintenance/delete_garbage_entries.py --apply
"""
import sqlite3, sys, os, re, time

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'churches.db')
DRY_RUN = '--dry-run' in sys.argv or '--apply' not in sys.argv

GARBAGE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r'^CHURCH HEALTH$', r'^CHURCH SECURITY$', r'^ANNUAL CHURCH PROFILE',
        r'^CHURCH PLANTING$', r'^CHURCH PLANT\b', r'^CHURCH GROWTH$',
        r'^CHURCH ADMIN', r'^CHURCH OFFICE', r'^CHURCH SURVEY',
        r'^CHURCH STATS', r'^CHURCH REPORT', r'^CHURCH DIRECTORY',
        r'^CHURCH LOANS', r'^CHURCH FINANCES', r'^CHURCH STRENGTHENING',
        r'^CHURCH CONSULTING', r'^CHURCH REVITALIZATION', r'^CHURCH RENEWAL',
        r'^CHURCH RESOURCES', r'^CHURCH LEADERSHIP', r'^CHURCH WEEKDAY',
        r'^CHURCH LOCATOR', r'^CHURCH OUTREACH', r'^CHURCH, CLERGY',
        r'^STRENGTHEN YOUR CHURCH', r'^MOBILIZE YOUR CHURCH',
        r'^PLANT A NEW CHURCH', r'^REVITALIZE AN EXISTING CHURCH',
        r'^BECOME A COOPERATING CHURCH', r'^FIND A BCI CHURCH',
        r'^ACCESS YOUR CHURCH', r'^RESOURCES FOR CHURCH',
        r'^STATEWIDE CHURCH LISTING', r'^COLLEGIATE INTERN',
        r'^SAFE CHURCH', r'^ALL CHURCH TRAINING',
        r'^SUNDAY SCHOOL', r'^BIBLE STUDY$', r'^YOUTH GROUP$',
        r'^YOUTH MINISTRY$', r'^CHILDREN', r'^KIDS MINISTRY',
        r'^WORSHIP TEAM', r'^PRAISE TEAM', r'^CHURCH STAFF',
        r'^OFFICE@', r'^INFO@', r'^CONTACT@', r'^PASTOR@',
        r'^CHURCH$', r'^CHURCHES$', r'^Episcopal Church$',
        r'^OPTIONS HEALTH', r'^RETA TRUST',
    ]
]

def is_garbage(name):
    if not name: return True
    for pat in GARBAGE_PATTERNS:
        if pat.match(name.strip()): return True
    return False

# Connect
db = sqlite3.connect(DB)
c = db.cursor()
all_ids = set()
details = []

# 1. Garbage pattern matches (no city, no GPS)
print("1. Pattern-matched garbage (no city, no GPS)...")
c.execute("""SELECT id, name, state, source FROM churches
    WHERE (city IS NULL OR city='') AND (latitude IS NULL OR latitude=0)
    AND country='US' ORDER BY id""")
for row in c.fetchall():
    if is_garbage(row[1]):
        all_ids.add(row[0])
        details.append((row[0], row[1], row[2], row[3], 'garbage_pattern'))
n1 = sum(1 for d in details if d[4] == 'garbage_pattern')
print(f"   {n1:,}")

# 2. csv_import triple-empty entries
print("2. csv_import triple-empty entries...")
c.execute("""SELECT id, name, state, source FROM churches
    WHERE (city IS NULL OR city='') AND (latitude IS NULL OR latitude=0)
    AND (address IS NULL OR address='') AND country='US'
    AND source='csv_import' ORDER BY id""")
added = 0
for row in c.fetchall():
    if row[0] not in all_ids:
        all_ids.add(row[0])
        details.append((row[0], row[1], row[2], row[3], 'csv_import_triple_empty'))
        added += 1
n2 = sum(1 for d in details if d[4] == 'csv_import_triple_empty')
print(f"   {n2:,} ({added:,} new)")

# Summary
print(f"\nTotal to delete: {len(all_ids):,}")

for label in ['garbage_pattern', 'csv_import_triple_empty']:
    group = [d for d in details if d[4] == label]
    if group:
        print(f"\n  {label} ({len(group):,}):")
        for d in group[:8]:
            nm = (d[1] or 'N/A')[:50]
            print(f"    [{d[0]}] {nm} | {d[2]}")

# Remaining triple-empty (kept)
exclude = ','.join(str(i) for i in all_ids) if all_ids else '0'
c.execute(f"""SELECT source, COUNT(*) FROM churches
    WHERE (city IS NULL OR city='') AND (latitude IS NULL OR latitude=0)
    AND (address IS NULL OR address='') AND country='US'
    AND id NOT IN ({exclude}) GROUP BY source ORDER BY 2 DESC""")
remaining = c.fetchall()
if remaining:
    total_rem = sum(r[1] for r in remaining)
    print(f"\nKept (triple-empty but from scrapers, not csv_import): {total_rem:,}")
    for src, n in remaining:
        print(f"  {src}: {n:,}")

# Orphaned
if all_ids:
    ph = ','.join('?' * len(all_ids))
    ids_list = list(all_ids)
    c.execute(f"SELECT COUNT(*) FROM church_contact_values WHERE church_id IN ({ph})", ids_list)
    print(f"\nOrphaned contacts: {c.fetchone()[0]:,}")
    c.execute(f"SELECT COUNT(*) FROM enrichment_change_log WHERE church_id IN ({ph})", ids_list)
    print(f"Orphaned enrichment logs: {c.fetchone()[0]:,}")

# Apply
if not DRY_RUN and all_ids:
    print(f"\nDELETING {len(all_ids):,} entries...")
    script_name = 'delete_garbage_entries'
    started = time.strftime('%Y-%m-%d %H:%M:%S')
    ph = ','.join('?' * len(all_ids))
    ids_list = list(all_ids)

    tables_cleaned = []
    for table in ['church_contact_values', 'enrichment_change_log',
                   'anglican_hierarchy', 'orthodox_hierarchy', 'lutheran_hierarchy',
                   'baptist_hierarchy', 'catholic_hierarchy', 'lds_hierarchy',
                   'jw_hierarchy', 'sa_hierarchy', 'moravian_hierarchy',
                   'ahmadiyya_hierarchy', 'chabad_hierarchy', 'bahai_hierarchy']:
        try:
            c.execute(f"DELETE FROM [{table}] WHERE church_id IN ({ph})", ids_list)
            if c.rowcount:
                tables_cleaned.append(f"{table}({c.rowcount})")
        except:
            pass

    for t in tables_cleaned:
        print(f"  FK: {t}")

    c.execute(f"DELETE FROM churches WHERE id IN ({ph})", ids_list)
    deleted = c.rowcount

    c.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated,
         fields_populated, status, notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        (script_name, script_name, started, time.strftime('%Y-%m-%d %H:%M:%S'),
         deleted, 'deleted', 'completed',
         f'Deleted {deleted} garbage entries. FK: {", ".join(tables_cleaned)}'))
    db.commit()

    print(f"\n  Churches deleted: {deleted:,}")
    print(f"  Provenance logged")
else:
    print("\nUse --apply to delete. Dry run only.")

db.close()
print("Done.")

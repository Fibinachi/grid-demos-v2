"""Clean up Armenian records: dedup + fix Congregational denomination misclassifications.

Usage:
  python _fix_armenian_dedup.py          # execute
  python _fix_armenian_dedup.py --dry-run # preview only

Phases:
  A. Fix denomination for Armenian Congregational churches (->United Church of Christ / Congregational)
  B. Overture_id duplicates -- delete extras
  C. Same name + same city + same state + coordinates within 0.001 deg -- keep best record
"""
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
import json
import sys

DRY_RUN = '--dry-run' in sys.argv
DB = 'churches.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
c = db.cursor()

def log_batch(script_name, churches_updated, churches_deleted, notes=""):
    c.execute(
        """INSERT INTO provenance_log 
           (source, script_name, started_at, completed_at, churches_updated, churches_inserted, fields_populated, parameters, records_attempted, records_matched, status, notes)
           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
        ('armenian_dedup', script_name,
         datetime.now(timezone.UTC).isoformat(), datetime.now(timezone.UTC).isoformat(),
         churches_updated, json.dumps(['denomination']), json.dumps({'dry_run': DRY_RUN}),
         0, 0, 'completed', notes)
    )

def score(m):
    s = 0
    if m['denomination'] and m['denomination'] != 'Unknown': s += 50
    if m['source'] and 'enrichment' in m['source']: s += 30
    if m['latitude'] is not None: s += 10
    return s

# Fetch all Armenian records
rows = c.execute(
    """SELECT rowid, name, faith, denomination, source, country, city, state,
              latitude, longitude, overture_id
       FROM churches 
       WHERE name LIKE '%Armenian%' OR name LIKE '%armenian%'
       ORDER BY name, country, city, state"""
).fetchall()
print(f"Total Armenian records: {len(rows)}")
if DRY_RUN:
    print("*** DRY RUN -- no changes will be made ***\n")

# ════════════════════════════════════════════════════════════════
# PHASE A: Fix Armenian Congregational denomination
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE A: Fix Armenian Congregational denomination misclassifications")
print("=" * 70)

CONGREGATIONAL_TERMS = ['CONGREGATIONAL']
corrected_list = []

for r in rows:
    name_upper = (r['name'] or '').upper()
    has_congregational = any(t in name_upper for t in CONGREGATIONAL_TERMS)
    
    if not has_congregational:
        continue
    
    new_denom = None
    current = r['denomination'] or ''
    
    if 'CALVARY' in name_upper:
        new_denom = 'United Church of Christ'
    elif 'UNITED' in name_upper:
        new_denom = 'United Church of Christ'
    elif 'CILICIA' in name_upper:
        new_denom = 'United Church of Christ'
    elif 'ARMENIAN MARTYRS' in name_upper:
        new_denom = 'Congregational'
    elif 'ARMENIAN MEMORIAL' in name_upper:
        new_denom = 'Congregational'
    elif 'IMMANUEL' in name_upper:
        new_denom = 'Congregational'
    elif 'PILGRIM' in name_upper:
        new_denom = 'Congregational'
    elif 'ARARAT' in name_upper:
        new_denom = 'United Church of Christ'
    elif name_upper == 'ARMENIAN CONGREGATIONAL CHURCH':
        new_denom = 'Congregational'
    
    if new_denom and current != new_denom:
        corrected_list.append((r['rowid'], current, new_denom, r['name'][:60]))
        if not DRY_RUN:
            c.execute("UPDATE churches SET denomination=? WHERE rowid=?", (new_denom, r['rowid']))

if corrected_list:
    print(f"  Corrected {len(corrected_list)} records:")
    for rid, old, new_nm, nm in corrected_list:
        print(f"    rowid={rid:>7} {old:35s} -> {new_nm:35s} | {nm}")
else:
    print("  None to fix (all already correct).")

all_deletions = []

# ════════════════════════════════════════════════════════════════
# PHASE B: Overture ID duplicates
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE B: Overture ID duplicates")
print("=" * 70)

rows = c.execute(
    """SELECT rowid, name, faith, denomination, source, country, city, state,
              latitude, longitude, overture_id
       FROM churches 
       WHERE name LIKE '%Armenian%' OR name LIKE '%armenian%'
       ORDER BY name, country, city, state"""
).fetchall()

oid_groups = defaultdict(list)
for r in rows:
    if r['overture_id']:
        oid_groups[r['overture_id']].append(r)

oid_dup_count = 0
for oid, group in oid_groups.items():
    if len(group) < 2:
        continue
    keeper = group[0]
    for d in group[1:]:
        all_deletions.append(d)
        oid_dup_count += 1
        print(f"  DELETE rowid={d['rowid']} (overture_id dup) -> KEEP rowid={keeper['rowid']}")

if not oid_dup_count:
    print("  No overture_id duplicates found.")

# ════════════════════════════════════════════════════════════════
# PHASE C: Same name + city + state + close coordinates
# ════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("PHASE C: Same name + city + state + close coords")
print("=" * 70)

ncs_groups = defaultdict(list)
for r in rows:
    key = (r['name'], r['country'], (r['city'] or '').strip().upper(), (r['state'] or '').strip().upper())
    ncs_groups[key].append(r)

coord_dup_count = 0
for key, group in ncs_groups.items():
    if len(group) < 2:
        continue
    name, country, city, state = key
    if not city or not state:
        continue
    
    # Sub-cluster by coordinate proximity
    clustered = []
    remaining = list(group)
    while remaining:
        anchor = remaining.pop(0)
        cluster = [anchor]
        still_remaining = []
        for r in remaining:
            if (r['latitude'] is not None and anchor['latitude'] is not None and
                abs(r['latitude'] - anchor['latitude']) <= 0.001 and
                abs(r['longitude'] - anchor['longitude']) <= 0.001):
                cluster.append(r)
            else:
                still_remaining.append(r)
        remaining = still_remaining
        if len(cluster) > 1:
            clustered.append(cluster)
    
    for cluster in clustered:
        sorted_cluster = sorted(cluster, key=score, reverse=True)
        keeper = sorted_cluster[0]
        for d in sorted_cluster[1:]:
            all_deletions.append(d)
            coord_dup_count += 1
            print(f"  DELETE rowid={d['rowid']:>7} src={d['source']:40s} -> KEEP rowid={keeper['rowid']:>7} src={keeper['source']:40s} | {name[:50]}")

if not coord_dup_count:
    print("  No duplicate groups found.")

# ════════════════════════════════════════════════════════════════
# EXECUTE
# ════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"{'DRY RUN - ' if DRY_RUN else ''}{len(all_deletions)} deletions")
print(f"{'DRY RUN - ' if DRY_RUN else ''}{len(corrected_list)} denomination fixes")

if DRY_RUN:
    print("Run without --dry-run to execute.")
else:
    for d in all_deletions:
        c.execute("DELETE FROM churches WHERE rowid=?", (d['rowid'],))
    db.commit()
    
    notes = (f"Deleted {len(all_deletions)} duplicates (overture_id: {oid_dup_count}, "
             f"coord: {coord_dup_count}). "
             f"Fixed {len(corrected_list)} Congregational denomination misclassifications.")
    log_batch('_fix_armenian_dedup.py', len(corrected_list), len(all_deletions), notes)
    db.commit()
    print(f"Deleted: {len(all_deletions)}")
    print(f"Denomination fixes: {len(corrected_list)}")

remaining = c.execute(
    "SELECT COUNT(*) FROM churches WHERE name LIKE '%Armenian%' OR name LIKE '%armenian%'"
).fetchone()[0]
print(f"Remaining Armenian records: {remaining}")

# Show corrected denominations
if not DRY_RUN and corrected_list:
    counted = c.execute("""
        SELECT denomination, COUNT(*) FROM churches
        WHERE (name LIKE '%Armenian%' OR name LIKE '%armenian%')
        AND denomination IS NOT NULL AND denomination != ''
        GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 5
    """).fetchall()
    print("\nTop denominations after cleanup:")
    for r in counted:
        print(f"  {r['denomination']}: {r['COUNT(*)']}")

db.close()

"""Fast batched dedup of enriched entries."""
import sqlite3
from collections import defaultdict

DB = r"E:\grid\churches.db"
CHUNK = 500

db = sqlite3.connect(DB, timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA synchronous=OFF")
c = db.cursor()

SRCS = ('irs+holy_sites_enrichment','overture_discovery+holy_sites_enrichment',
        'overture_full+holy_sites_enrichment','csv_import+holy_sites_enrichment',
        'masstimes_nationwide+holy_sites_enrichment','pcusa_api+holy_sites_enrichment',
        'ou_api+holy_sites_enrichment')

print("Loading...", end=" ", flush=True)
ph = ','.join(['?']*len(SRCS))
rows = c.execute(f"""SELECT id, name, country, CASE WHEN latitude IS NOT NULL THEN 1 ELSE 0 END,
    CASE WHEN address IS NOT NULL AND address!='' THEN 1 ELSE 0 END, landmark_type
    FROM churches WHERE source IN ({ph}) ORDER BY name, country, id""", SRCS).fetchall()
print(f"{len(rows):,}")

print("Grouping...", end=" ", flush=True)
groups = defaultdict(list)
for r in rows:
    groups[(r[1], r[2])].append(r)
dupes = {k: v for k, v in groups.items() if len(v) > 1}
to_remove = sum(len(v)-1 for v in dupes.values())
print(f"{len(dupes):,} clusters, {to_remove:,} to remove")

def score(r):
    s = 0
    if r[3]: s += 5
    if r[4]: s += 3
    if r[5] and r[5] != 'organization': s += 2
    return s

delete_ids = []
for k, entries in dupes.items():
    entries.sort(key=lambda r: (score(r), -r[0]), reverse=True)
    for e in entries[1:]:
        delete_ids.append(e[0])

print(f"\nDeleting {len(delete_ids):,} dupes...")
for i in range(0, len(delete_ids), CHUNK):
    batch = delete_ids[i:i+CHUNK]
    ph_b = ','.join(['?']*len(batch))
    c.execute(f"DELETE FROM churches WHERE id IN ({ph_b})", batch)
    db.commit()
    print(f"\r  {min(i+CHUNK, len(delete_ids)):,}/{len(delete_ids):,}", end="", flush=True)

for tbl in ['enrichment_change_log','classification_history','church_contact_values']:
    c.execute(f"DELETE FROM {tbl} WHERE church_id NOT IN (SELECT id FROM churches)")
    print(f"\n  Cleaned {tbl}: {c.rowcount:,}")

c.execute("SELECT COUNT(1) FROM churches")
print(f"\nTotal: {c.fetchone()[0]:,}")
db.execute("PRAGMA synchronous=NORMAL")
db.close()
print("Done!")

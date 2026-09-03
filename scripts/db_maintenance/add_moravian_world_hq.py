"""
Add the Moravian World HQ (Herrnhut, Germany) and restructure the hierarchy.

The Unitas Fratrum (Worldwide Moravian Church) has its historic center in
Herrnhut, Germany. The "Christliches Zentrum Herrnhut" (Christian Center
Herrnhut) at Zinzendorfplatz 1 serves as the administrative center.

New hierarchy:
  World HQ (Herrnhut, DE)
    ├── Northern Province (Bethlehem, PA)
    │     └── US congregations (northern states)
    ├── Southern Province (Winston-Salem, NC)
    │     └── US congregations (southern states)
    ├── Canadian District (Calgary)
    │     └── CA congregations
    ├── Jamaica Province
    │     └── JM congregations
    ├── European Continental Province (Herrnhut)
    │     └── DE congregations (future)
    └── Other provinces (future: GB, ZA, etc.)

Usage:
    python scripts/db_maintenance/add_moravian_world_hq.py
    python scripts/db_maintenance/add_moravian_world_hq.py --dry-run
"""
import sqlite3, sys
from datetime import datetime

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=120)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=120000")
c = db.cursor()

# The existing entry in Herrnhut we'll use as the HQ anchor
# Christliches Zentrum Herrnhut - at Zinzendorfplatz area, Herrnhut
WORLD_HQ_CHURCH_ID = 4118613

# Province HQ church IDs (already in moravian_hierarchy)
PROVINCE_IDS = {
    'northern': 5040297,      # Central Moravian Church Office Building
    'southern': 4994208,      # Christ Moravian Office (Winston-Salem)
    'canadian': 2298546,      # BOARD OF ELDERS OF THE CANADIAN DISTRICT
    'jamaica': 3294465,       # Jamaica Province of the Moravian Church
}

print("=" * 60)
print("Add Moravian World HQ")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Step 1: Verify the HQ candidate entry
print("\n[1/5] Verifying World HQ candidate entry...")
hq_church = c.execute("""
    SELECT id, name, city, country, latitude, longitude, faith
    FROM churches WHERE id = ?
""", (WORLD_HQ_CHURCH_ID,)).fetchone()

if hq_church:
    print(f"  Found: #{hq_church[0]} {hq_church[1][:50]}")
    print(f"    Location: {hq_church[2]}, {hq_church[3]}")
    print(f"    Coords: {hq_church[4]:.4f}, {hq_church[5]:.4f}")
    print(f"    Faith: {hq_church[6]}")
else:
    print(f"  ERROR: Entry #{WORLD_HQ_CHURCH_ID} not found!")
    sys.exit(1)

# Step 2: Fix faith if needed (should be Christian)
if hq_church[6] in ('Other', None, ''):
    print("\n[2/5] Fixing faith on HQ entry...")
    if not dry_run:
        c.execute("UPDATE churches SET faith = 'Christian' WHERE id = ?", (WORLD_HQ_CHURCH_ID,))
        db.commit()
    print(f"  {hq_church[6]} → Christian")
else:
    print(f"\n[2/5] Faith already set: {hq_church[6]}")

# Step 3: Add HQ node to moravian_hierarchy (if not already there)
print("\n[3/5] Adding World HQ node to hierarchy...")
existing_hq = c.execute("""
    SELECT id FROM moravian_hierarchy
    WHERE church_id = ? AND moravian_type = 'hq'
""", (WORLD_HQ_CHURCH_ID,)).fetchone()

if existing_hq:
    print(f"  World HQ already in hierarchy (id={existing_hq[0]})")
    world_hq_hid = existing_hq[0]
else:
    if not dry_run:
        c.execute("""
            INSERT INTO moravian_hierarchy
                (church_id, name, moravian_type, moravian_detail, city, country, lat, lon)
            VALUES (?, ?, 'hq', 'Unitas Fratrum / Worldwide Moravian Church',
                    'Herrnhut', 'DE', ?, ?)
        """, (WORLD_HQ_CHURCH_ID, hq_church[1], hq_church[4], hq_church[5]))
        world_hq_hid = c.lastrowid
        db.commit()
    else:
        world_hq_hid = -1
    print(f"  World HQ added to hierarchy (id={world_hq_hid})")

# Step 4: Link province HQs under World HQ
print("\n[4/5] Linking province HQs under World HQ...")
if not dry_run:
    for name, church_id in PROVINCE_IDS.items():
        phq = c.execute("""
            SELECT id FROM moravian_hierarchy
            WHERE church_id = ? AND moravian_type = 'province_hq'
        """, (church_id,)).fetchone()
        if phq:
            # Only link if not already linked
            current_parent = c.execute(
                "SELECT parent_id FROM moravian_hierarchy WHERE id = ?", (phq[0],)
            ).fetchone()
            if current_parent and current_parent[0] != world_hq_hid:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'hq', relationship = 'administered_by'
                    WHERE id = ?
                """, (world_hq_hid, phq[0]))
                print(f"  {name:12s}: #{phq[0]} → World HQ")
            elif current_parent and current_parent[0] == world_hq_hid:
                print(f"  {name:12s}: #{phq[0]} already linked to World HQ")
            else:
                c.execute("""
                    UPDATE moravian_hierarchy
                    SET parent_id = ?, parent_moravian_type = 'hq', relationship = 'administered_by'
                    WHERE id = ?
                """, (world_hq_hid, phq[0]))
                print(f"  {name:12s}: #{phq[0]} → World HQ (was orphan)")
        else:
            print(f"  WARNING: {name} province HQ not in hierarchy!")
    db.commit()
else:
    for name in PROVINCE_IDS:
        print(f"  Would link {name} → World HQ")

# Step 5: Link DE entries to European Continental Province
# The European Continental Province is headquartered in Herrnhut
# So DE entries could go under the World HQ directly or under a European node
# For now, link DE entries directly to World HQ
print("\n[5/5] Linking German entries directly to World HQ...")
# Exclude entries that are the same church as the HQ itself
de_entries = c.execute("""
    SELECT h.id, h.name, h.moravian_type, h.city
    FROM moravian_hierarchy h
    WHERE h.country = 'DE' AND h.moravian_type != 'province_hq'
      AND h.church_id != ?
      AND (h.parent_id IS NULL OR h.parent_id != ?)
""", (WORLD_HQ_CHURCH_ID, world_hq_hid)).fetchall()

if de_entries:
    print(f"  Found {len(de_entries)} German entries to link...")
    if not dry_run:
        linked = 0
        for hid, name, mtype, city in de_entries:
            c.execute("""
                UPDATE moravian_hierarchy
                SET parent_id = ?, parent_moravian_type = 'hq', relationship = 'administered_by'
                WHERE id = ?
            """, (world_hq_hid, hid))
            linked += 1
        db.commit()
        print(f"  ✓ {linked} German entries linked to World HQ")
    else:
        print(f"  Would link {len(de_entries)} German entries")
else:
    print("  No German entries to link")

# Summary
print(f"\n{'='*60}")
print("FINAL STATE")
print(f"{'='*60}")

total = c.execute("SELECT COUNT(*) FROM moravian_hierarchy").fetchone()[0]
linked = c.execute("SELECT COUNT(*) FROM moravian_hierarchy WHERE parent_id IS NOT NULL").fetchone()[0]
orphans = total - linked

print(f"Total moravian_hierarchy: {total:,}")
print(f"Linked: {linked:,}")
print(f"Unlinked (orphans): {orphans:,}")

# Count by province
for name, cid in [('World HQ (Herrnhut)', WORLD_HQ_CHURCH_ID),
                    *[(f'{n} Province', cid) for n, cid in PROVINCE_IDS.items()]]:
    cnt = c.execute("""
        SELECT COUNT(*) FROM moravian_hierarchy
        WHERE parent_id = (SELECT id FROM moravian_hierarchy WHERE church_id = ?)
    """, (cid,)).fetchone()[0]
    print(f"  Under {name:30s}: {cnt}")

# Top orphans
print(f"\nTop unlinked countries:")
for r in c.execute("""
    SELECT h.country, COUNT(*) FROM moravian_hierarchy h
    WHERE h.parent_id IS NULL AND h.moravian_type != 'hq' AND h.moravian_type != 'province_hq'
    GROUP BY h.country ORDER BY COUNT(*) DESC LIMIT 10
"""):
    print(f"  {r[0] or 'None':15s}: {r[1]}")

if not dry_run:
    now = datetime.now().isoformat()
    c.execute("""
        INSERT INTO provenance_log (source, script_name, started_at,
                                     churches_updated, status)
        VALUES ('moravian_world_hq', 'add_moravian_world_hq.py', ?,
                ?, 'completed')
    """, (now, linked))
    db.commit()

db.close()
print("\nDone.")

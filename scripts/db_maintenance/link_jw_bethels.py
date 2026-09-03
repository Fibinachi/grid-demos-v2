"""
Link Assembly Halls to their country's Bethel (branch office).

Hierarchy:
  Bethel / Branch Office (country-level admin)
    └── Assembly Hall (regional, affiliated_with → Bethel)
          └── Kingdom Hall (local, served_by → AH)

Usage:
    python scripts/db_maintenance/link_jw_bethels.py              # run for real
    python scripts/db_maintenance/link_jw_bethels.py --dry-run     # preview
"""
import sqlite3, sys

CHUNK = 500
dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=60000")
c = db.cursor()


def normalize(s):
    if s is None:
        return ''
    return s.strip().lower()


print("=" * 60)
print("JW Bethel → Assembly Hall Linking")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Load bethels
bethels = c.execute("""
    SELECT id, name, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'bethel'
    ORDER BY id
""").fetchall()
print(f"\nLoaded {len(bethels)} bethel entries")

# Load assembly halls (only ones without parent_id already)
halls = c.execute("""
    SELECT id, name, city, state, country
    FROM jw_hierarchy
    WHERE jw_type = 'assembly_hall'
    ORDER BY id
""").fetchall()
print(f"Loaded {len(halls)} assembly halls")

# Build bethel lookup by country
bethel_lookup = {}  # {country_norm: [bethel_rows]}
for b in bethels:
    key = normalize(b[4])
    bethel_lookup.setdefault(key, []).append(b)

print(f"  Bethels in {len(bethel_lookup)} countries")

# Match AHs to bethels by country
links = []  # [(ah_id, bethel_id, bethel_name), ...]
unlinked = []

for ah in halls:
    ahid, ahname, ahcity, ahstate, ahcountry = ah
    key = normalize(ahcountry)
    candidates = bethel_lookup.get(key, [])
    
    if len(candidates) == 1:
        links.append((ahid, candidates[0][0], candidates[0][1]))
    elif len(candidates) > 1:
        # Multiple bethels in same country — pick first
        links.append((ahid, candidates[0][0], candidates[0][1]))
    else:
        unlinked.append(ah)

# Summary
by_country = {}
for ahid, bid, bname in links:
    bkey = (bid, bname[:30])
    by_country.setdefault(bkey, []).append(ahid)

print(f"\nMatching results:")
print(f"  Linked: {len(links)} AHs to {len(by_country)} bethels")
print(f"  Unlinked: {len(unlinked)} AHs")

for (bid, bname), ah_ids in sorted(by_country.items(), key=lambda x: -len(x[1])):
    print(f"    Bethel #{bid} {bname:40s} → {len(ah_ids)} AHs")

if unlinked:
    print(f"\n  Unlinked AHs by country:")
    cnts = {}
    for ah in unlinked:
        cnts[ah[4] or '?'] = cnts.get(ah[4] or '?', 0) + 1
    for ccode, cnt in sorted(cnts.items(), key=lambda x: -x[1]):
        print(f"    {ccode}: {cnt} AHs (no bethel)")

# Apply
print(f"\nApplying links...")
if dry_run:
    print(f"  Would update {len(links)} AHs (parent_id → bethel, relationship='affiliated_with')")
else:
    updated = 0
    for ahid, bid, bname in links:
        c.execute(
            "UPDATE jw_hierarchy SET parent_id = ?, relationship = 'affiliated_with' WHERE id = ?",
            (bid, ahid)
        )
        updated += 1
    db.commit()
    print(f"  ✓ Updated {updated} AHs")

    # Verify
    linked_ahs = c.execute(
        "SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type='assembly_hall' AND parent_id IS NOT NULL"
    ).fetchone()[0]
    print(f"  Assembly halls with parent: {linked_ahs}")
    
    rels = c.execute(
        "SELECT relationship, COUNT(*) FROM jw_hierarchy WHERE relationship IS NOT NULL GROUP BY relationship"
    ).fetchall()
    for r, cnt in rels:
        print(f"    {r}: {cnt}")

db.close()
print("\nDone.")

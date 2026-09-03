"""
Link all bethels (branch offices) to the world headquarters.

JW structure: Governing Body / World HQ → Branch Offices (Bethels)

The HQ entry already exists in jw_hierarchy as:
  #16976 WORLD HEADQUARTERS OF Jehovah's WITNESSES (Warwick, NY)

Usage:
    python scripts/db_maintenance/link_jw_hq.py              # run for real
    python scripts/db_maintenance/link_jw_hq.py --dry-run     # preview
"""
import sqlite3, sys

dry_run = '--dry-run' in sys.argv

db = sqlite3.connect(r'E:\grid\churches.db', timeout=30)
db.execute("PRAGMA journal_mode=WAL")
db.execute("PRAGMA busy_timeout=60000")
c = db.cursor()

print("=" * 60)
print("JW Bethel → World HQ Linking")
if dry_run:
    print("  *** DRY RUN — no changes will be made ***")
print("=" * 60)

# Find the HQ entry
hq = c.execute("""
    SELECT id, name, city, state, country, jw_type
    FROM jw_hierarchy WHERE id = 16976
""").fetchone()

if not hq:
    print("\n❌ HQ entry (#16976) not found!")
    db.close()
    sys.exit(1)

print(f"\nWorld HQ: #{hq[0]} {hq[1]}")
print(f"  Location: {hq[2]}, {hq[3]} {hq[4]}")
print(f"  Current type: {hq[5]}")

# Get all other bethels
bethels = c.execute("""
    SELECT id, name, city, state, country, parent_id
    FROM jw_hierarchy
    WHERE jw_type = 'bethel' AND id != 16976
    ORDER BY id
""").fetchall()
print(f"\nOther bethels to link: {len(bethels)}")

# Show what will be linked
already_linked = 0
to_link = []
for b in bethels:
    if b[5] == 16976:
        already_linked += 1
    else:
        to_link.append(b)
        print(f"  #{b[0]} {b[1][:50]:50s} | {str(b[2]):15s} {str(b[3]):2s} {b[4]}")

print(f"\n  Already linked to HQ: {already_linked}")
print(f"  To link: {len(to_link)}")

# Apply
print(f"\nApplying...")
if dry_run:
    print(f"  Would reclassify HQ as jw_type='bethel'")
    print(f"  Would link {len(to_link)} bethels to HQ")
else:
    # Reclassify HQ as bethel
    c.execute("UPDATE jw_hierarchy SET jw_type = 'bethel' WHERE id = 16976")
    print(f"  ✓ Reclassified HQ as bethel")
    
    # Link all other bethels to HQ
    for b in to_link:
        c.execute(
            "UPDATE jw_hierarchy SET parent_id = 16976, relationship = 'affiliated_with' WHERE id = ?",
            (b[0],)
        )
    db.commit()
    print(f"  ✓ Linked {len(to_link)} bethels to HQ")
    
    # Verify
    print(f"\nVerification:")
    bethel_count = c.execute("SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type='bethel'").fetchone()[0]
    print(f"  Total bethels: {bethel_count}")
    
    linked_bethels = c.execute(
        "SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type='bethel' AND parent_id = 16976"
    ).fetchone()[0]
    print(f"  Bethels linked to HQ: {linked_bethels}")
    
    # Full chain count
    print(f"\nFull hierarchy chain:")
    print(f"  HQ → {linked_bethels} bethels → ...")
    ah_linked = c.execute(
        "SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type='assembly_hall' AND parent_id IS NOT NULL"
    ).fetchone()[0]
    print(f"  → {ah_linked} assembly halls")
    kh_linked = c.execute(
        "SELECT COUNT(*) FROM jw_hierarchy WHERE jw_type='kingdom_hall' AND parent_id IS NOT NULL"
    ).fetchone()[0]
    print(f"  → {kh_linked:,} Kingdom Halls")

db.close()
print("\nDone.")

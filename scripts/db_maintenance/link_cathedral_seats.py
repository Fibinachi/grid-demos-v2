"""
Link Catholic cathedral seats (bishop's seats) to their parent dioceses in catholic_hierarchy.

Strategy:
1. Build a name→ID map from catholic_hierarchy for diocese/archdiocese entries
2. For each Catholic cathedral with enrichment.diocese, normalize the diocese name
   (St.→Saint, special overrides for typos) and match to the hierarchy
3. Update existing hierarchy rows (set parent_id, fix cath_type) or insert new rows
4. Log all changes to provenance_log and enrichment_change_log

Usage: python scripts/db_maintenance/link_cathedral_seats.py [--dry-run]
"""

import sqlite3
import sys
import re
from datetime import datetime

DB_PATH = "churches.db"
CHUNK_SIZE = 500

# Manual override map for enrichment diocese values that don't match hierarchy names
# even after St.→Saint normalization
DIOCESE_OVERRIDES = {
    "Bismark": "Diocese of Bismarck",
    "Joliet": "Diocese of Joliet in Illinois",
    "Kingston (Canada)": "Archdiocese of Kingston",
    "Lafayette in Louisiana": "Diocese of Lafayette",
    "Portland in Maine": "Diocese of Portland",
}

# Also handle St.→Saint exceptions where the short name needs the prefix
PREFIX_LOOKUP: dict[str, str] = {}  # short_name -> full_hierarchy_name


def normalize_diocese_name(name: str) -> str:
    """Normalize a diocese name for matching against catholic_hierarchy."""
    n = name.strip()
    # St. → Saint (hierarchy uses "Saint")
    n = re.sub(r'\bSt\.\s*', 'saint ', n, flags=re.I)
    n = re.sub(r'\bSt\s+', 'saint ', n, flags=re.I)
    # Standardize dashes
    n = n.replace(" - ", "-")
    n = n.replace(" – ", "-")
    return n


def build_diocese_map(c):
    """Build a map from normalized names to hierarchy IDs for diocese/archdiocese entries."""
    c.execute("""
        SELECT id, name, cath_type FROM catholic_hierarchy
        WHERE cath_type IN ('diocese', 'archdiocese', 'eparchy', 'archeparchy')
    """)
    rows = c.fetchall()

    # Map: normalized_name → (id, original_name, cath_type)
    diocese_map = {}
    for hid, hname, htype in rows:
        norm = normalize_diocese_name(hname.lower().strip())
        diocese_map[norm] = (hid, hname, htype)
        # Also index by the short name (without "Diocese of"/"Archdiocese of" prefix)
        for prefix in ["archdiocese of ", "diocese of ", "eparchy of ", "archeparchy of "]:
            if norm.startswith(prefix):
                short = norm[len(prefix):]
                if short not in diocese_map:
                    diocese_map[short] = (hid, hname, htype)
                break

    # Build prefix lookup: short name → full hierarchy name
    for norm, (hid, hname, htype) in diocese_map.items():
        for prefix in ["archdiocese of ", "diocese of ", "eparchy of ", "archeparchy of "]:
            if norm.startswith(prefix):
                short = norm[len(prefix):]
                PREFIX_LOOKUP[short] = norm
                break

    return diocese_map


def find_diocese_id(diocese_map, enrichment_value: str):
    """Find hierarchy diocese/archdiocese ID matching an enrichment diocese value."""
    # Check override first
    if enrichment_value in DIOCESE_OVERRIDES:
        target = DIOCESE_OVERRIDES[enrichment_value]
        norm = normalize_diocese_name(target.lower().strip())
        if norm in diocese_map:
            return diocese_map[norm]
        # Try without prefix
        for prefix in ["archdiocese of ", "diocese of ", "eparchy of ", "archeparchy of "]:
            if norm.startswith(prefix):
                short = norm[len(prefix):]
                if short in diocese_map:
                    return diocese_map[short]
                break

    # Normalize and try direct match
    norm = normalize_diocese_name(enrichment_value.lower().strip())
    if norm in diocese_map:
        return diocese_map[norm]

    # Try with "Diocese of " prefix
    with_prefix = "diocese of " + norm
    if with_prefix in diocese_map:
        return diocese_map[with_prefix]

    # Try with "Archdiocese of " prefix
    with_arch = "archdiocese of " + norm
    if with_arch in diocese_map:
        return diocese_map[with_arch]

    # Try without any prefix (if enrichment already has a prefix)
    for prefix in ["archdiocese of ", "diocese of ", "eparchy of ", "archeparchy of "]:
        if norm.startswith(prefix):
            short = norm[len(prefix):]
            if short in diocese_map:
                return diocese_map[short]
            break

    return None


def get_existing_hierarchy_rows(c, church_ids):
    """Get catholic_hierarchy rows for a set of church_ids."""
    if not church_ids:
        return {}
    placeholders = ",".join("?" for _ in church_ids)
    c.execute(f"""
        SELECT church_id, id, cath_type, parent_id, name
        FROM catholic_hierarchy
        WHERE church_id IN ({placeholders})
    """, list(church_ids))
    result = {}
    for row in c.fetchall():
        result[row[0]] = {"hier_id": row[1], "cath_type": row[2],
                          "parent_id": row[3], "name": row[4]}
    return result


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("🔶 DRY RUN MODE — no changes will be made\n")

    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    timestamp = datetime.now().isoformat()

    # Step 1: Build diocese name map
    print("Building diocese name map...")
    diocese_map = build_diocese_map(c)
    print(f"  {len(diocese_map)} diocese/archdiocese name variants indexed")

    # Step 2: Get all Catholic cathedrals with enrichment.diocese
    print("\nFetching Catholic cathedrals with diocese data...")
    c.execute("""
        SELECT ct.id AS church_id, ct.name AS church_name,
               ct.city, ct.state, ct.country,
               e.diocese, e.diocese_detail
        FROM churches ct
        JOIN church_enrichment e ON e.church_id = ct.id
        WHERE ct.landmark_type = 'cathedral'
          AND ct.legacy = 'Catholic'
          AND e.diocese IS NOT NULL AND e.diocese != ''
        ORDER BY e.diocese
    """)
    cathedrals = c.fetchall()
    print(f"  {len(cathedrals)} cathedrals to process")

    # Step 3: Get existing hierarchy rows for these churches
    church_ids = [r[0] for r in cathedrals]
    existing_hier = get_existing_hierarchy_rows(c, church_ids)
    print(f"  {len(existing_hier)} already have hierarchy rows")

    # Step 4: Match each cathedral to its diocese
    matched = 0
    unmatched = 0
    to_update = []  # (hier_id, parent_id, needs_type_fix, church_id, diocese_name)
    to_insert = []  # (church_id, church_name, diocese_id, diocese_name, ...)

    for church_id, church_name, city, state, country, diocese_val, diocese_detail in cathedrals:
        result = find_diocese_id(diocese_map, diocese_val)
        if result is None:
            if unmatched < 10:
                print(f"  ⚠ UNMATCHED: diocese='{diocese_val}' → church #{church_id} '{church_name[:40]}'")
            unmatched += 1
            continue

        dio_id, dio_name, dio_type = result
        matched += 1

        if church_id in existing_hier:
            hier_row = existing_hier[church_id]
            hier_id = hier_row["hier_id"]
            needs_type_fix = (hier_row["cath_type"] != "cathedral")
            to_update.append((hier_id, dio_id, needs_type_fix, church_id, dio_name))
        else:
            to_insert.append((church_id, church_name, dio_id, dio_name, city, state, country))

    print(f"\n  Matched: {matched}")
    print(f"  Unmatched: {unmatched}")

    if unmatched > 0:
        print("\n  Full list of unmatched diocese values:")
        unmatched_vals = set()
        for church_id, church_name, city, state, country, diocese_val, diocese_detail in cathedrals:
            result = find_diocese_id(diocese_map, diocese_val)
            if result is None:
                unmatched_vals.add(diocese_val)
        for v in sorted(unmatched_vals):
            print(f"    '{v}'")

    # Step 5: Apply updates
    print(f"\n{'='*60}")
    print(f"APPLYING CHANGES:")
    print(f"  Update existing hierarchy rows: {len(to_update)}")
    print(f"  Insert new cathedral rows: {len(to_insert)}")
    print(f"{'='*60}")

    if dry_run:
        # Show sample
        if to_update:
            print(f"\n  Sample updates (first 5):")
            for hier_id, parent_id, needs_fix, cid, dname in to_update[:5]:
                fix_flag = " [needs cath_type fix]" if needs_fix else ""
                print(f"    hier#{hier_id} → parent={parent_id} ({dname}){fix_flag}")
        if to_insert:
            print(f"\n  Sample inserts (first 5):")
            for cid, cname, did, dname, city, st, country in to_insert[:5]:
                print(f"    church#{cid} '{cname[:40]}' → parent={did} ({dname})")
        db.close()
        print("\n✅ Dry run complete. Pass --dry-run to preview, omit to execute.")
        return

    # --- REAL EXECUTION ---
    enrichment_entries = []

    # 5a: Update existing hierarchy rows
    updated_count = 0
    for hier_id, parent_id, needs_type_fix, church_id, dio_name in to_update:
        if needs_type_fix:
            c.execute("""
                UPDATE catholic_hierarchy
                SET parent_id = ?, cath_type = 'cathedral',
                    parent_cath_type = 'diocese',
                    relationship = 'seat_of'
                WHERE id = ?
            """, (parent_id, hier_id))
        else:
            c.execute("""
                UPDATE catholic_hierarchy
                SET parent_id = ?,
                    parent_cath_type = 'diocese',
                    relationship = 'seat_of'
                WHERE id = ?
            """, (parent_id, hier_id))
        updated_count += 1

        enrichment_entries.append((church_id, "parent_id", "NULL", str(parent_id),
                                   "link_cathedral_seats"))

        if updated_count % CHUNK_SIZE == 0:
            db.commit()
            print(f"  Updated {updated_count}/{len(to_update)}...")

    db.commit()
    print(f"  Updated {updated_count} existing hierarchy rows")

    # 5b: Insert new cathedral rows
    inserted_count = 0
    for church_id, church_name, dio_id, dio_name, city, state, country in to_insert:
        c.execute("""
            INSERT INTO catholic_hierarchy
                (parent_id, church_id, name, cath_type, cath_detail,
                 diocese, city, state, country,
                 parent_cath_type, relationship, notes)
            VALUES (?, ?, ?, 'cathedral', 'bishop_seat',
                    ?, ?, ?, ?,
                    'diocese', 'seat_of', 'Linked from enrichment.diocese')
        """, (dio_id, church_id, church_name[:200],
              dio_name, city or "", state or "", country or ""))
        new_id = c.lastrowid
        inserted_count += 1

        enrichment_entries.append((church_id, "hierarchy_id", "NULL", str(new_id),
                                   "link_cathedral_seats"))

        if inserted_count % CHUNK_SIZE == 0:
            db.commit()
            print(f"  Inserted {inserted_count}/{len(to_insert)}...")

    db.commit()
    print(f"  Inserted {inserted_count} new cathedral rows")

    # 5c: Log provenance (summary row in provenance_log)
    print("\nLogging provenance...")
    c.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted, fields_populated,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    """, ("link_cathedral_seats", "link_cathedral_seats.py",
          timestamp, datetime.now().isoformat(),
          updated_count, inserted_count,
          "parent_id,cath_type,parent_cath_type,relationship",
          len(cathedrals), matched,
          f"Unmatched: {unmatched}. Diocese coverage: {updated_count+inserted_count}/677 with data."))

    # Log per-church changes to enrichment_change_log
    for church_id, field_name, old_val, new_val, change_source in enrichment_entries:
        c.execute("""
            INSERT INTO enrichment_change_log
                (church_id, field_name, old_value, new_value, change_source)
            VALUES (?, ?, ?, ?, ?)
        """, (church_id, field_name, old_val, new_val, change_source))

    db.commit()
    print(f"  Provenance summary logged")
    print(f"  {len(enrichment_entries)} enrichment change entries logged")

    # Step 6: Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Total cathedrals processed: {len(cathedrals)}")
    print(f"  Matched to diocese: {matched}")
    print(f"  Unmatched: {unmatched}")
    print(f"  Hierarchy rows updated: {updated_count}")
    print(f"  New hierarchy rows inserted: {inserted_count}")

    if unmatched > 0:
        print(f"\n  ⚠ Unmatched diocese values ({unmatched} cathedrals affected):")
        unmatched_vals = set()
        for church_id, church_name, city, state, country, diocese_val, diocese_detail in cathedrals:
            result = find_diocese_id(diocese_map, diocese_val)
            if result is None:
                unmatched_vals.add(diocese_val)
        for v in sorted(unmatched_vals):
            print(f"    '{v}'")

    # Count dioceses now with cathedral
    c.execute("""
        SELECT COUNT(DISTINCT parent_id) FROM catholic_hierarchy
        WHERE cath_type = 'cathedral' AND parent_id IS NOT NULL
    """)
    covered = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM catholic_hierarchy WHERE cath_type IN ('diocese','archdiocese')")
    total_dioceses = c.fetchone()[0]
    print(f"\n  Dioceses with a cathedral seat: {covered} / {total_dioceses} ({covered*100//max(total_dioceses,1)}%)")

    db.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    main()

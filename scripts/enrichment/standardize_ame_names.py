"""
Standardize AME (African Methodist Episcopal) church naming conventions.

Changes:
  AME (standalone)  → A.M.E.    (e.g., "BETHEL AME CHURCH" → "BETHEL A.M.E. CHURCH")
  AMEC              → A.M.E.    (e.g., "ALLEN CHAPEL AMEC" → "ALLEN CHAPEL A.M.E.")
  AMEZ              → A.M.E. ZION   (e.g., "BELL AMEZ CHURCH" → "BELL A.M.E. ZION CHURCH")
  AME ZION          → A.M.E. ZION   (e.g., "ZION HILL AME ZION CHURCH" → "ZION HILL A.M.E. ZION CHURCH")
  A M E             → A.M.E.    (e.g., "MOUNT ZION A M E CHURCH" → "MOUNT ZION A.M.E. CHURCH")

Usage:
    python scripts/enrichment/standardize_ame_names.py

Provenance:
    - enrichment_change_log entries for each name change
    - provenance_log entry
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect, Provenance, log_changes_batch

CHUNK_SIZE = 500
SCRIPT_NAME = "standardize_ame_names"


def find_ame_records(db) -> list[tuple]:
    """Find all records with AME naming that needs standardization.
    Returns list of (rowid, church_id, old_name, new_name)."""
    c = db.cursor()

    # We'll search for multiple patterns and combine results
    patterns = []

    # Pattern 1: Standalone "AME" (word boundary, case-insensitive)
    # Matches " AME ", " AME" at end, "AME " at start, but NOT AMERICAN, CAME, NAME, etc.
    c.execute("""
        SELECT rowid, id, name FROM churches
        WHERE (name LIKE '% AME %'
            OR name LIKE '% AME'
            OR name LIKE 'AME %'
            OR name LIKE '% AMEZ %'
            OR name LIKE '% AMEZ'
            OR name LIKE 'AMEZ %'
            OR name LIKE '% AMEC %'
            OR name LIKE '% AMEC'
            OR name LIKE 'AMEC %'
            OR name LIKE '% AME ZION%'
            OR name LIKE '% A M E %'
            OR name LIKE '% A M E'
            OR name LIKE 'A M E %')
        AND name NOT LIKE '%A.M.E.%'
        AND name NOT LIKE '%AFRICAN METHODIST EPISCOPAL%'
        ORDER BY rowid
    """)

    results = []
    for row in c.fetchall():
        rowid, church_id, old_name = row
        if not old_name:
            continue

        new_name = old_name

        # Order matters: handle longer patterns first

        # AMEZ → A.M.E. ZION (before standalone AME to avoid double-processing)
        new_name = re.sub(r'\bAMEZ\b', 'A.M.E. ZION', new_name, flags=re.IGNORECASE)

        # AMEC → A.M.E. (AME Church → A.M.E.)
        new_name = re.sub(r'\bAMEC\b', 'A.M.E.', new_name, flags=re.IGNORECASE)

        # AME ZION → A.M.E. ZION
        new_name = re.sub(r'\bAME\s+ZION\b', 'A.M.E. ZION', new_name, flags=re.IGNORECASE)

        # Standalone AME → A.M.E.
        new_name = re.sub(r'\bAME\b', 'A.M.E.', new_name, flags=re.IGNORECASE)

        # A M E → A.M.E. (spaces instead of dots)
        new_name = re.sub(r'\bA\s+M\s+E\b', 'A.M.E.', new_name, flags=re.IGNORECASE)

        if new_name != old_name:
            results.append((rowid, church_id, old_name, new_name))

    return results


def update_church_name(db, rowid, new_name):
    """Update a single church name."""
    c = db.cursor()
    c.execute("UPDATE churches SET name = ? WHERE rowid = ?", (new_name, rowid))


def main():
    db = connect()

    print("Scanning for AME naming variations...")
    records = find_ame_records(db)
    print(f"Found {len(records):,} records to standardize")

    if not records:
        print("Nothing to do.")
        return

    # Show breakdown
    simple_ame = sum(1 for r in records if 'AME' in r[2] and 'A.M.E.' not in r[2])
    amec = sum(1 for r in records if 'AMEC' in r[2])
    amez = sum(1 for r in records if 'AMEZ' in r[2])
    ame_zion = sum(1 for r in records if 'AME ZION' in r[2])
    a_m_e = sum(1 for r in records if 'A M E' in r[2])
    print(f"  Standalone AME → A.M.E.:  ~{simple_ame:,}")
    print(f"  AMEC → A.M.E.:            ~{amec:,}")
    print(f"  AMEZ → A.M.E. ZION:       ~{amez:,}")
    print(f"  AME ZION → A.M.E. ZION:   ~{ame_zion:,}")
    print(f"  A M E → A.M.E.:           ~{a_m_e:,}")

    # Preview a sample
    print("\n=== Sample changes ===")
    for r in records[:10]:
        print(f"  rowid={r[0]} | {r[2][:60]:60s} → {r[3]}")

    # Ask for confirmation via input would be ideal, but we'll just proceed
    print(f"\nProceeding with {len(records):,} updates...")

    with Provenance(db, SCRIPT_NAME, source="name_standardization",
                     action="updated", fields="name",
                     records_attempted=len(records)) as prov:

        changes = []
        for i, (rowid, church_id, old_name, new_name) in enumerate(records):
            update_church_name(db, rowid, new_name)
            changes.append((church_id or rowid, "name", old_name, new_name))
            prov.churches_updated += 1

            if (i + 1) % CHUNK_SIZE == 0:
                db.commit()
                log_changes_batch(db, changes, source=SCRIPT_NAME)
                changes = []
                print(f"  ... {i+1:,} updated")

        # Final commit and log remaining changes
        db.commit()
        if changes:
            log_changes_batch(db, changes, source=SCRIPT_NAME)
            db.commit()

    print(f"\n✅ {len(records):,} AME names standardized")
    print(f"Changes logged to enrichment_change_log + provenance_log")


if __name__ == "__main__":
    main()

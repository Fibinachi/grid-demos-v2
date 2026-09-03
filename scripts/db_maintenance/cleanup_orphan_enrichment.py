#!/usr/bin/env python3
"""
Clean up orphaned church_enrichment records (church_id not in churches table).
Uses provenance tracking via gw_db.

Usage:
    python scripts/db_maintenance/cleanup_orphan_enrichment.py [--dry-run]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from gw_db import connect, Provenance

SCRIPT_NAME = "cleanup_orphan_enrichment.py"
SOURCE_NAME = "db_maintenance"

def main():
    parser = argparse.ArgumentParser(description="Delete orphaned church_enrichment records")
    parser.add_argument("--dry-run", action="store_true", help="Count orphans but don't delete")
    args = parser.parse_args()

    conn = connect("churches.db")
    c = conn.cursor()

    # Count orphans
    c.execute("""
        SELECT COUNT(*) FROM church_enrichment ce
        LEFT JOIN churches ch ON ch.id = ce.church_id
        WHERE ch.id IS NULL
    """)
    orphan_count = c.fetchone()[0]
    print(f"Orphaned church_enrichment records: {orphan_count:,}")

    # Count valid
    c.execute("SELECT COUNT(*) FROM church_enrichment")
    total = c.fetchone()[0]
    print(f"Total church_enrichment records: {total:,}")
    print(f"Would remain: {total - orphan_count:,}")

    if orphan_count == 0:
        print("No orphans to clean up.")
        return

    if args.dry_run:
        print("\nDry run — no changes made.")
        return

    # Delete orphans in batches with provenance
    BATCH_SIZE = 5000
    deleted_total = 0
    batch_num = 0

    print(f"\nDeleting orphans in batches of {BATCH_SIZE:,}...")
    start_time = time.time()

    while True:
        c.execute("""
            SELECT ce.church_id FROM church_enrichment ce
            LEFT JOIN churches ch ON ch.id = ce.church_id
            WHERE ch.id IS NULL
            LIMIT ?
        """, (BATCH_SIZE,))
        batch = [row[0] for row in c.fetchall()]
        if not batch:
            break

        placeholders = ",".join("?" * len(batch))
        c.execute(f"DELETE FROM church_enrichment WHERE church_id IN ({placeholders})", batch)
        deleted = c.rowcount

        with Provenance(conn, SCRIPT_NAME, source=SOURCE_NAME,
                         fields=f"church_id (deleted)",
                         records_attempted=len(batch)) as prov:
            prov.records_matched = deleted
            prov.churches_updated = deleted

        deleted_total += deleted
        batch_num += 1
        print(f"  Batch {batch_num}: deleted {deleted:,} (total: {deleted_total:,})")

        conn.commit()

    elapsed = time.time() - start_time
    print(f"\nDone! Deleted {deleted_total:,} orphan records in {elapsed:.0f}s")

    # Verify
    c.execute("""
        SELECT COUNT(*) FROM church_enrichment ce
        LEFT JOIN churches ch ON ch.id = ce.church_id
        WHERE ch.id IS NULL
    """)
    remaining = c.fetchone()[0]
    print(f"Remaining orphans: {remaining:,}")

    c.execute("SELECT COUNT(*) FROM church_enrichment")
    print(f"Total church_enrichment after cleanup: {c.fetchone()[0]:,}")

    conn.close()

if __name__ == "__main__":
    start_time = time.time()
    main()

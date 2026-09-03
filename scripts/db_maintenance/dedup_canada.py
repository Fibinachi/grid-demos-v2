"""
Deduplicate Canadian records — same-source, same-name, same-coord duplicates.

Preserves CRA records (kept for financial data continuity).
Removes one record from each duplicate pair where the same source
imported the same church at the same coordinates twice.

Usage:
    python scripts/db_maintenance/dedup_canada.py             # live
    python scripts/db_maintenance/dedup_canada.py --dry-run   # preview only
"""

import re, sys, sqlite3
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CHUNK = 500

# Sources to exclude from dedup (keep all)
EXCLUDE_SOURCES_RE = re.compile(r'^cra_')


def get_db():
    db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=OFF")  # safety during batch delete
    return db


def log_provenance(db, script_name, started_at, churches_deleted, notes):
    cur = db.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, 'rowid', 'completed', ?)
    """, ('dedup_canada.py', script_name, started_at, now, churches_deleted, notes))
    db.commit()


def progress_bar(current, total, label=''):
    if total == 0:
        return
    pct = current * 100 // total
    bar_len = 40
    filled = pct * bar_len // 100
    bar = chr(9608) * filled + chr(9617) * (bar_len - filled)
    print(f'\r  {label} [{bar}] {pct:3d}% ({current:,}/{total:,})', end='', flush=True)
    if current >= total:
        print()


def compute_keep_score(row):
    """Score a record for how worth keeping it is (higher = better)."""
    name, city, address, denom, faith, landmark_type, osm_id, wikidata_qid, source_primary = row
    score = 0
    if city and city.strip():
        score += 2
    if address and address.strip():
        score += 3
    if denom and denom.strip():
        score += 1
    if faith and faith.strip():
        score += 1
    if landmark_type and landmark_type.strip():
        score += 1
    if osm_id and osm_id.strip():
        score += 1
    if wikidata_qid and wikidata_qid.strip():
        score += 1
    if source_primary and source_primary.strip():
        score += 1
    return score


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Deduplicate Canada ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    # Find same-source, same-name, same-coord duplicate groups (non-CRA)
    print("\nFinding duplicate groups...", flush=True)
    c.execute("""
        SELECT name, source, ROUND(latitude,5), ROUND(longitude,5), COUNT(*) as cnt
        FROM churches
        WHERE country='CA'
          AND latitude IS NOT NULL
          AND source NOT LIKE 'cra_%'
        GROUP BY name, source, ROUND(latitude,5), ROUND(longitude,5)
        HAVING cnt > 1
        ORDER BY cnt DESC
    """)
    groups = c.fetchall()
    print(f"  Found {len(groups):,} duplicate groups", flush=True)

    total_dup_records = sum(g[4] for g in groups)
    print(f"  Total records in groups: {total_dup_records:,}", flush=True)

    if not groups:
        print("  No duplicates found.", flush=True)
        db.close()
        return

    # Columns that can be merged from duplicate into kept record
    # (name/coords are identical by definition; source-specific IDs merge in case one is richer)
    MERGE_COLS = [
        'address', 'city', 'state', 'zip', 'zip5', 'zip4',
        'denomination', 'faith', 'faith_tradition', 'landmark_type',
        'osm_id', 'osm_type', 'wikidata_qid', 'overture_id',
        'source_primary', 'source_secondary',
        'ein', 'ntee_code', 'cra_bn',
        'county', 'county_fips_5', 'confidence_score',
    ]

    to_delete = []  # list of (rowid, name, source)
    merges_performed = 0

    for idx, (name, source, lat, lon, cnt) in enumerate(groups):
        if (idx + 1) % 100 == 0 or idx == 0:
            progress_bar(idx + 1, len(groups), 'Analyzing groups')

        c.execute("""
            SELECT rowid, name, city, address, denomination, faith,
                   landmark_type, osm_id, wikidata_qid, source_primary
            FROM churches
            WHERE country='CA'
              AND name=?
              AND source=?
              AND ROUND(latitude,5)=?
              AND ROUND(longitude,5)=?
            ORDER BY rowid
        """, (name, source, lat, lon))
        rows = c.fetchall()

        # Score each record
        scored = [(compute_keep_score(r[1:]), r[0], r[1]) for r in rows]
        scored.sort(key=lambda x: (-x[0], x[1]))
        keep_rowid = scored[0][1]

        # Fetch full data for merge candidates
        c.execute(f"SELECT rowid, {','.join(MERGE_COLS)} FROM churches WHERE rowid=?", (keep_rowid,))
        target_row = c.fetchone()

        for score, dup_rowid, rname in scored[1:]:
            # Fetch duplicate's data
            c.execute(f"SELECT rowid, {','.join(MERGE_COLS)} FROM churches WHERE rowid=?", (dup_rowid,))
            dup_row = c.fetchone()

            if not DRY_RUN:
                # Build SET clause for columns where dup has data but target doesn't
                updates = []
                merge_details = []
                for ci, col in enumerate(MERGE_COLS):
                    tval = target_row[ci + 1]  # offset for rowid
                    dval = dup_row[ci + 1]
                    t_has = tval is not None and str(tval).strip() != ''
                    d_has = dval is not None and str(dval).strip() != ''
                    if d_has and not t_has:
                        updates.append(f"{col}=?")
                        merge_details.append(f"{col}: {tval} -> {dval}")

                if updates:
                    # Apply merge
                    vals = [dup_row[ci + 1] for ci, col in enumerate(MERGE_COLS) if
                            (target_row[ci + 1] is None or str(target_row[ci + 1]).strip() == '')
                            and (dup_row[ci + 1] is not None and str(dup_row[ci + 1]).strip() != '')]
                    set_clause = ', '.join(updates)
                    c.execute(f"UPDATE churches SET {set_clause} WHERE rowid=?", vals + [keep_rowid])
                    db.commit()

                    # Log merge to enrichment_change_log
                    for detail in merge_details:
                        field, rest = detail.split(': ', 1)
                        old_v, new_v = rest.split(' -> ')
                        c.execute("""
                            INSERT INTO enrichment_change_log
                                (church_id, field_name, old_value, new_value, change_source, changed_at)
                            VALUES (?, ?, ?, ?, 'dedup_merge', datetime('now'))
                        """, (keep_rowid, field, old_v, new_v))
                    db.commit()
                    merges_performed += 1

            to_delete.append((dup_rowid, rname, source))

    progress_bar(len(groups), len(groups), 'Analyzing groups')

    total_to_delete = len(to_delete)
    total_keep = total_dup_records - total_to_delete
    print(f"\n  Will delete: {total_to_delete:,} records, keep: {total_keep:,}", flush=True)
    print(f"  Merges performed: {merges_performed:,}", flush=True)

    if total_to_delete == 0:
        print("  Nothing to delete.", flush=True)
        db.close()
        return

    if DRY_RUN:
        print(f"\n  Sample deletions (first 15):", flush=True)
        for rowid, name, source in to_delete[:15]:
            print(f"    DELETE rowid={rowid} | {name[:55]:55s} | {source[:30]}", flush=True)
    else:
        # Delete in batches
        print(f"\nDeleting {total_to_delete:,} records...", flush=True)
        deleted = 0
        for i in range(0, len(to_delete), CHUNK):
            batch = to_delete[i:i + CHUNK]
            rowids = tuple(r[0] for r in batch)
            placeholders = ','.join(['?'] * len(rowids))
            c.execute(f"DELETE FROM churches WHERE rowid IN ({placeholders})", rowids)
            deleted += len(batch)
            db.commit()
            progress_bar(deleted, total_to_delete, 'Deleting')

        # Log provenance
        note_parts = [
            f'Deduplicated {total_to_delete:,} records from {len(groups):,} groups',
            f'({merges_performed:,} merges performed before delete)',
        ]
        log_provenance(db, 'dedup_canada.py', started_at, total_to_delete, '; '.join(note_parts))
        print(f"\n  Provenance logged.", flush=True)

    # Summary
    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Groups processed: {len(groups):,}", flush=True)
    print(f"  Records deleted:  {total_to_delete:,}", flush=True)
    print(f"  Records kept:     {total_keep:,}", flush=True)
    print(f"  Merges performed: {merges_performed:,}", flush=True)
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()

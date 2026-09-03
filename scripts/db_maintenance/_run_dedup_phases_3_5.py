"""
GPS dedup — Phase 3a/3b/4/5 only.
Uses existing _gps_dedup_map (from Phase 1-2).
Skips the GROUP_CONCAT source merge that crashed.
"""
import sqlite3, time
from datetime import datetime, timezone

DB = r'E:\grid\churches.db'

OTO_TABLES = ['church_enrichment', 'church_contacts']
MTO_TABLES = [
    'church_classification_meta', 'church_broadband',
    'church_sources', 'enrichment_change_log',
]

def get_conn():
    conn = sqlite3.connect(DB, timeout=120)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn


def phase_3a_repoint_mto(conn):
    """Re-point many-to-one child tables: simple survivor_id update."""
    print('[Phase 3a] Re-pointing many-to-one child tables...')
    totals = {}
    for table in MTO_TABLES:
        t0 = time.time()
        refs = conn.execute(
            f'SELECT COUNT(*) FROM {table} '
            f'WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)'
        ).fetchone()[0]
        if refs == 0:
            print(f'  {table}: 0 refs ({time.time()-t0:.2f}s)')
            totals[table] = 0
            continue
        conn.execute(f'''
            UPDATE {table} SET church_id = (
                SELECT survivor_id FROM _gps_dedup_map
                WHERE dupe_id = {table}.church_id
            )
            WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)
        ''')
        conn.commit()
        elapsed = time.time() - t0
        print(f'  {table}: {refs:,} rows repointed ({elapsed:.2f}s)')
        totals[table] = refs
    return totals


def phase_3b_merge_oto(conn):
    """Handle 1:1 child tables — merge + delete dupe rows."""
    print('[Phase 3b] Handling 1:1 child tables (merge + repoint)...')
    totals = {}
    for table in OTO_TABLES:
        t0 = time.time()

        # Re-point rows where survivor does NOT already have a row
        conn.execute(f'''
            UPDATE {table} SET church_id = (
                SELECT survivor_id FROM _gps_dedup_map
                WHERE dupe_id = {table}.church_id
            )
            WHERE church_id IN (
                SELECT m.dupe_id FROM _gps_dedup_map m
                LEFT JOIN {table} t1 ON t1.church_id = m.survivor_id
                WHERE t1.church_id IS NULL
            )
        ''')
        repointed = conn.execute('SELECT changes()').fetchone()[0]
        conn.commit()

        # Handle conflicts: both survivor and dupe have a row
        conflict_pairs = conn.execute(f'''
            SELECT DISTINCT m.survivor_id, m.dupe_id
            FROM _gps_dedup_map m
            JOIN {table} t1 ON t1.church_id = m.survivor_id
            JOIN {table} t2 ON t2.church_id = m.dupe_id
        ''').fetchall()

        merged = 0
        if conflict_pairs:
            data_cols = [
                r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()
                if r[1] not in ('id', 'church_id')
            ]

            for survivor_id, dupe_id in conflict_pairs:
                surv_row = conn.execute(
                    f'SELECT * FROM {table} WHERE church_id = ?', (survivor_id,)
                ).fetchone()
                dupe_row = conn.execute(
                    f'SELECT * FROM {table} WHERE church_id = ?', (dupe_id,)
                ).fetchone()
                if not surv_row or not dupe_row:
                    continue

                col_names = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
                updates = {}
                for i, col in enumerate(col_names):
                    if col in ('id', 'church_id'):
                        continue
                    if surv_row[i] is None and dupe_row[i] is not None:
                        updates[col] = dupe_row[i]

                if updates:
                    set_clause = ', '.join(f'"{c}" = ?' for c in updates)
                    vals = list(updates.values()) + [survivor_id]
                    conn.execute(
                        f'UPDATE {table} SET {set_clause} WHERE church_id = ?', vals
                    )
                    merged += 1

            # Delete dupe rows
            dupe_ids = list(set(p[1] for p in conflict_pairs))
            if len(dupe_ids) == 1:
                conn.execute(f'DELETE FROM {table} WHERE church_id = ?', (dupe_ids[0],))
            else:
                conn.execute(
                    f'DELETE FROM {table} WHERE church_id IN ({",".join(str(d) for d in dupe_ids)})'
                )
            conn.commit()

        elapsed = time.time() - t0
        print(f'  {table}: {repointed:,} repointed, {merged:,} merged, '
              f'{len(conflict_pairs):,} conflicts deleted ({elapsed:.2f}s)')
        totals[table] = {'repointed': repointed, 'merged': merged, 'conflicts': len(conflict_pairs)}
    return totals


def phase_4_delete_dupes(conn):
    """Delete duplicate church records in batches."""
    print('[Phase 4] Deleting duplicate records...')
    t0 = time.time()
    total = 0
    batch = 0
    while True:
        conn.execute('''
            DELETE FROM churches WHERE id IN (
                SELECT dupe_id FROM _gps_dedup_map LIMIT 50000
            )
        ''')
        deleted = conn.execute('SELECT changes()').fetchone()[0]
        conn.commit()
        total += deleted
        batch += 1
        if deleted == 0:
            break
        if batch % 5 == 0:
            print(f'  Deleted {total:,}... ({time.time()-t0:.0f}s)')
    print(f'  Deleted {total:,} in {time.time()-t0:.1f}s')
    return total


def phase_5_log_provenance(conn, stats, deleted):
    """Log the dedup to provenance_log and drop temp table."""
    print('[Phase 5] Logging provenance...')
    notes = (
        f'GPS dedup at 5dp. '
        f'{deleted:,} duplicates merged into {stats["groups"]:,} survivors. '
        f'MTO: {",".join(MTO_TABLES)}, OTO: {",".join(OTO_TABLES)}'
    )
    conn.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, records_attempted, records_matched,
             status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    ''', (
        'gps_dedup', '_run_dedup_phases_3_5.py',
        stats['started_at'], datetime.now(timezone.utc).isoformat(),
        deleted, deleted, stats['groups'], notes
    ))
    conn.commit()
    print('  Provenance logged.')

    # Drop temp table
    conn.execute('DROP TABLE IF EXISTS _gps_dedup_map')
    conn.commit()
    print('  _gps_dedup_map dropped.')
    return notes


def main():
    started_at = datetime.now(timezone.utc)
    print('=' * 60)
    print('GPS Dedup — Phases 3a/3b/4/5')
    print('=' * 60)
    print(f'Started: {started_at.isoformat()}')
    print(f'DB: {DB}')
    print()

    conn = get_conn()

    # Verify dedup map exists
    map_count = conn.execute(
        'SELECT COUNT(*) FROM _gps_dedup_map'
    ).fetchone()[0]
    print(f'_gps_dedup_map has {map_count:,} rows')
    survivors = conn.execute(
        'SELECT COUNT(DISTINCT survivor_id) FROM _gps_dedup_map'
    ).fetchone()[0]
    print(f'{survivors:,} unique survivor groups')

    before = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    print(f'Churches before: {before:,}')
    print()

    stats = {
        'groups': survivors,
        'dupes': map_count - survivors,
        'started_at': started_at.isoformat(),
    }

    # Phase 3a
    t0 = time.time()
    mto_totals = phase_3a_repoint_mto(conn)
    print(f'  Phase 3a done in {time.time()-t0:.1f}s')
    print()

    # Phase 3b
    t0 = time.time()
    oto_totals = phase_3b_merge_oto(conn)
    print(f'  Phase 3b done in {time.time()-t0:.1f}s')
    print()

    # Phase 4
    t0 = time.time()
    deleted = phase_4_delete_dupes(conn)
    print(f'  Phase 4 done in {time.time()-t0:.1f}s')
    print()

    # Phase 5
    phase_5_log_provenance(conn, stats, deleted)

    # Summary
    after = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    print(f'\n{"=" * 60}')
    print(f'GPS Dedup Complete')
    print(f'{"=" * 60}')
    print(f'  Survivors:    {survivors:,}')
    print(f'  Deleted:      {deleted:,}')
    print(f'  Before:       {before:,}')
    print(f'  After:        {after:,}')
    print(f'  Reduction:    {before - after:,}')
    print(f'  Elapsed:      {elapsed:.0f}s')
    print(f'{"=" * 60}')

    conn.close()


if __name__ == '__main__':
    main()

"""
Phase 5: Log provenance for GPS dedup operation.

Records what was done in the provenance_log table.
"""
import sqlite3
from datetime import datetime, timezone

DB = r'E:\grid\churches.db'

def main():
    print(f'{"="*60}')
    print(f'  Phase 5 — Log Provenance')
    print(f'{"="*60}')

    conn = sqlite3.connect(DB, timeout=60)

    # Gather stats
    before = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    map_cnt = conn.execute('SELECT COUNT(*) FROM _gps_dedup_map').fetchone()[0]
    groups = conn.execute('SELECT COUNT(DISTINCT group_id) FROM _gps_dedup_map').fetchone()[0]
    survivors = conn.execute('SELECT COUNT(DISTINCT survivor_id) FROM _gps_dedup_map').fetchone()[0]

    print(f'\n  Churches after dedup: {before:,}')
    print(f'  Dedup map rows: {map_cnt:,}')
    print(f'  Groups: {groups:,}')
    print(f'  Survivors: {survivors:,}')

    # Orphan check for all child tables
    orphan_tables = [
        ('church_enrichment', 'church_id'),
        ('church_contacts', 'church_id'),
        ('church_classification_meta', 'church_id'),
        ('church_broadband', 'church_id'),
        ('church_sources', 'church_id'),
        ('enrichment_change_log', 'church_id'),
    ]
    total_orphans = 0
    for tbl, col in orphan_tables:
        n = conn.execute(
            f'SELECT COUNT(*) FROM {tbl} t LEFT JOIN churches c ON c.id = t.{col} WHERE c.id IS NULL'
        ).fetchone()[0]
        if n:
            print(f'  Orphaned {tbl}: {n:,}')
            total_orphans += n
    if total_orphans == 0:
        print(f'  Child tables: all clean (0 orphans)')

    deleted = conn.execute(
        'SELECT COUNT(DISTINCT dupe_id) FROM _gps_dedup_map WHERE dupe_id != 0 AND dupe_id != survivor_id'
    ).fetchone()[0]
    notes = (
        f'GPS dedup at 5dp. '
        f'{deleted:,} duplicates merged into {survivors:,} survivors. '
        f'OTO: church_enrichment,church_contacts, '
        f'MTO: church_classification_meta,church_broadband,church_sources,enrichment_change_log'
    )

    conn.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, records_attempted, records_matched,
             status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    ''', (
        'gps_dedup', '_gps_dedup_mem.py',
        datetime.now(timezone.utc).isoformat(),
        datetime.now(timezone.utc).isoformat(),
        deleted, deleted, survivors, notes
    ))
    conn.commit()
    print(f'\n  ✅ Provenance logged')

    # Clean up dedup map table
    conn.execute('DROP TABLE IF EXISTS _gps_dedup_map')
    conn.commit()
    print(f'  ✅ Dedup map table cleaned up')

    # Final integrity check
    print('\n  Running integrity check...', end=' ', flush=True)
    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    print(f'{integrity}')

    conn.close()
    print(f'\n{"="*60}')
    print(f'  GPS Dedup — COMPLETE')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

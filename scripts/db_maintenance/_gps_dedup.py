"""
GPS-based deduplication for churches.db.

Strategy (per user request):
- Group by ROUND(latitude, 5), ROUND(longitude, 5) (~1.1m precision)
- Per group: keep the record with the most non-null columns as "survivor"
- Re-point all child table references from dupes → survivor
- Merge non-null data from dupes into survivor (fill NULLs on survivor)
- Delete duplicate records
- Log all operations in provenance_log

Batch processing to avoid long transactions and allow resume.
"""

import sqlite3
import sys
import os
import time
from datetime import datetime

DB = r'E:\grid\churches.db'
BATCH_SIZE = 5000          # Groups per batch
MERGE_COMMIT_FREQ = 500    # Commit frequency during merge phase

# ─── Child tables ────────────────────────────────────────────────────────────
# Each entry: (table_name, church_id_column, is_one_to_one, priority)
# is_one_to_one: True = survivor typically has at most 1 row → merge or delete dupe's row
# priority: higher = this child table's data is more valuable to keep
CHILD_TABLES = [
    # One-to-one: need to merge or drop dupe rows
    ('church_contacts',       'church_id', True,  80),
    ('church_enrichment',     'church_id', True,  90),
    ('church_classification_meta', 'church_id', True,  60),
    ('church_broadband',      'church_id', True,  50),
    # Many-to-one: just re-point
    ('church_sources',        'church_id', False, 70),
    ('enrichment_change_log', 'church_id', False, 40),
    ('church_fcc',            'church_id', True,  30),
    ('church_gnis',           'church_id', True,  30),
    ('church_nrhp',           'church_id', True,  30),
    ('church_postal_admin',   'church_id', True,  30),
    ('church_metro_area',     'church_id', True,  30),
]

# ─── Columns to merge (fill NULLs on survivor from dupes) ────────────────────
# Skip id, source (handled separately), and derived geo columns
MERGE_COLUMNS = [
    'name', 'denomination', 'family', 'faith', 'faith_tradition',
    'tradition_legacy', 'subtradition', 'religion_type',
    'normalized_name', 'address', 'city', 'state', 'zip', 'zip5', 'zip4',
    'ein', 'ntee_code', 'geocode_source', 'fips', 'country',
    'denomination_affiliation', 'address_source',
    'landmark_type', 'heritage_status', 'height_m', 'width_m', 'length_m',
    'area_m2', 'capacity', 'building_year', 'source_primary', 'source_secondary',
    'osm_id', 'osm_type', 'overture_id', 'confidence_score',
    'cra_bn', 'cra_category', 'cra_sub_category', 'cra_designation',
    'mosque_type', 'canonical_status', 'heritage_source', 'dedication',
    'muslim_affiliation', 'muslim_confidence', 'muslim_classification_source',
    'muslim_updated', 'name_original', 'age_centuries', 'county', 'county_fips_5',
    'name_transliterated',
]


def get_conn():
    conn = sqlite3.connect(DB)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')  # ~800 MB cache
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn


def ensure_temp_table(conn):
    """Create temp dedup map table if not exists."""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _gps_dedup_map (
            group_id    INTEGER,
            survivor_id INTEGER,
            dupe_id     INTEGER,
            PRIMARY KEY (group_id, dupe_id)
        )
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_dedup_map_dupe 
        ON _gps_dedup_map(dupe_id)
    ''')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_dedup_map_survivor 
        ON _gps_dedup_map(survivor_id)
    ''')


def count_gps_groups(conn):
    """Count total GPS duplicate groups."""
    return conn.execute('''
        SELECT COUNT(*) FROM (
            SELECT ROUND(latitude,5) as lat, ROUND(longitude,5) as lon
            FROM churches
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            GROUP BY lat, lon
            HAVING COUNT(*) > 1
        )
    ''').fetchone()[0]


def compute_scores_and_groups(conn, offset=0, limit=5000):
    """
    For a batch of GPS groups, compute non-null scores and determine survivors.
    Returns list of dicts: {group_id, survivor_id, dupe_id}
    """
    # Get a batch of group keys (lat, lon)
    group_keys = conn.execute('''
        SELECT ROUND(latitude,5) as lat, ROUND(longitude,5) as lon, COUNT(*) as cnt
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        GROUP BY lat, lon
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, lat, lon
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()

    if not group_keys:
        return []

    # Build list of all IDs in these groups to score them
    placeholders = []
    params = []
    for lat, lon, cnt in group_keys:
        placeholders.append('(ROUND(latitude,5) = ? AND ROUND(longitude,5) = ?)')
        params.extend([lat, lon])

    where_clause = ' OR '.join(placeholders)

    # Score each row by non-null count
    non_null_expr = ' + '.join(
        f'(CASE WHEN "{col}" IS NOT NULL THEN 1 ELSE 0 END)'
        for col in [r[1] for r in conn.execute('PRAGMA table_info(churches)').fetchall()
                     if r[1] not in ('id',)]
    )

    rows = conn.execute(f'''
        SELECT id, ROUND(latitude,5) as lat, ROUND(longitude,5) as lon,
               {non_null_expr} as score
        FROM churches
        WHERE {where_clause}
        ORDER BY lat, lon, score DESC
    ''', params).fetchall()

    # Group by (lat, lon) and pick survivor (first = highest score due to ORDER BY score DESC)
    groups = {}
    for row_id, lat, lon, score in rows:
        key = (lat, lon)
        if key not in groups:
            groups[key] = {'group_id': len(groups), 'survivor_id': row_id, 'dupes': []}
        else:
            groups[key]['dupes'].append(row_id)

    # Build flat map
    dedup_map = []
    for key, g in groups.items():
        for dupe_id in g['dupes']:
            dedup_map.append({
                'group_id': g['group_id'],
                'survivor_id': g['survivor_id'],
                'dupe_id': dupe_id,
            })

    return dedup_map


def insert_dedup_map(conn, dedup_map):
    """Insert dedup map entries in batch."""
    conn.executemany(
        'INSERT OR IGNORE INTO _gps_dedup_map (group_id, survivor_id, dupe_id) '
        'VALUES (:group_id, :survivor_id, :dupe_id)',
        dedup_map
    )
    conn.commit()


def repoint_child_table(conn, table, church_col):
    """Re-point child table rows from dupe IDs to survivor IDs."""
    t0 = time.time()
    affected = conn.execute(f'''
        UPDATE {table} SET {church_col} = (
            SELECT survivor_id FROM _gps_dedup_map 
            WHERE dupe_id = {table}.{church_col}
        )
        WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
    ''')
    rows = conn.execute(f'''
        SELECT COUNT(*) FROM {table}
        WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
    ''').fetchone()[0]
    conn.commit()
    elapsed = time.time() - t0
    return rows, elapsed


def merge_columns(conn):
    """Merge data from dupes into survivors: fill NULLs on survivor from dupes."""
    t0 = time.time()
    total_updates = 0

    for col in MERGE_COLUMNS:
        # For each column, find survivors that have NULL but a dupe has a value
        # Use a subquery to get the first non-NULL value from any dupe
        affected = conn.execute(f'''
            UPDATE churches SET "{col}" = (
                SELECT d."{col}" FROM _gps_dedup_map m
                JOIN churches d ON d.id = m.dupe_id
                WHERE m.survivor_id = churches.id
                  AND d."{col}" IS NOT NULL
                LIMIT 1
            )
            WHERE id IN (SELECT DISTINCT survivor_id FROM _gps_dedup_map)
              AND "{col}" IS NULL
        ''')
        updated = conn.execute('SELECT changes()').fetchone()[0]
        if updated:
            total_updates += updated

        if total_updates > 0 and total_updates % MERGE_COMMIT_FREQ == 0:
            conn.commit()

    conn.commit()
    elapsed = time.time() - t0
    return total_updates, elapsed


def merge_source_field(conn):
    """Merge source field: append dupe source info to survivor."""
    t0 = time.time()
    # For each survivor, collect distinct source values from its dupes
    sources = conn.execute('''
        SELECT m.survivor_id, GROUP_CONCAT(DISTINCT d.source, '|')
        FROM _gps_dedup_map m
        JOIN churches d ON d.id = m.dupe_id
        WHERE d.source IS NOT NULL AND d.source != ''
        GROUP BY m.survivor_id
    ''').fetchall()

    count = 0
    for survivor_id, dupe_sources in sources:
        if not dupe_sources:
            continue
        current = conn.execute(
            'SELECT source FROM churches WHERE id = ?', (survivor_id,)
        ).fetchone()
        if current and current[0]:
            existing = set(current[0].split('|'))
        else:
            existing = set()

        new_sources = [s for s in dupe_sources.split('|') if s and s not in existing]
        if new_sources:
            merged = '|'.join(sorted(existing | set(new_sources)))
            conn.execute(
                'UPDATE churches SET source = ? WHERE id = ?',
                (merged, survivor_id)
            )
            count += 1

    conn.commit()
    elapsed = time.time() - t0
    return count, elapsed


def delete_dupes(conn):
    """Delete all dupe records from churches table."""
    t0 = time.time()
    result = conn.execute('''
        DELETE FROM churches WHERE id IN (SELECT dupe_id FROM _gps_dedup_map)
    ''')
    deleted = conn.execute('SELECT changes()').fetchone()[0]
    conn.commit()
    elapsed = time.time() - t0
    return deleted, elapsed


def log_provenance(conn, total_groups, deleted_count, started_at):
    """Log provenance for the dedup operation."""
    t0 = time.time()

    # Log summary row to provenance_log (batch-level table)
    conn.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, churches_inserted,
             records_attempted, records_matched, status, notes)
        VALUES (?, ?, ?, ?,
                ?, 0,
                ?, ?, 'completed', ?)
    ''', (
        'gps_dedup', '_gps_dedup.py', started_at, datetime.now().isoformat(),
        deleted_count,  # churches_updated = survivors that received data
        deleted_count,  # records_attempted = dupes removed
        total_groups,   # records_matched = groups processed
        f'GPS dedup at 5dp precision. {deleted_count} duplicates merged into {total_groups} survivors. '
        f'Child tables repointed: church_sources, church_contacts, church_enrichment, '
        f'church_classification_meta, church_broadband.'
    ))
    conn.commit()
    elapsed = time.time() - t0
    return elapsed


def handle_oto_child_tables(conn):
    """
    For one-to-one child tables, when both survivor and dupe have rows,
    merge data from dupe's row into survivor's row, then delete dupe's row.
    """
    results = {}

    for table, church_col, is_oto, priority in CHILD_TABLES:
        if not is_oto:
            continue

        t0 = time.time()
        if table == 'church_contacts' or table == 'church_enrichment':
            # Get columns (skip id and church_id)
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()
                    if r[1] not in ('id', church_col)]

        # Step 1: Identify survivors that have a row AND their dupes also have a row
        if table == 'church_contacts':
            survivors_with_data = conn.execute(f'''
                SELECT DISTINCT m.survivor_id
                FROM _gps_dedup_map m
                JOIN {table} t1 ON t1.{church_col} = m.survivor_id
                JOIN {table} t2 ON t2.{church_col} = m.dupe_id
            ''').fetchall()

            if not survivors_with_data:
                # No conflicts - just re-point
                affected = conn.execute(f'''
                    UPDATE {table} SET {church_col} = (
                        SELECT survivor_id FROM _gps_dedup_map
                        WHERE dupe_id = {table}.{church_col}
                    )
                    WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
                ''')
                conn.commit()
                results[table] = {'action': 'repoint', 'rows': 0, 'elapsed': time.time() - t0}
                continue

            # For each conflicting survivor, merge data from dupe's contact row
            survivor_ids = [s[0] for s in survivors_with_data]
            merged = 0

            # For each survivor with data, update dupe contact rows to point to survivor
            # (creating multiple contact rows per church, which is valid)
            conn.execute(f'''
                UPDATE {table} SET {church_col} = (
                    SELECT survivor_id FROM _gps_dedup_map
                    WHERE dupe_id = {table}.{church_col}
                )
                WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
            ''')
            conn.commit()
            results[table] = {'action': 'repoint+merge', 'rows': 0, 'elapsed': time.time() - t0}

        elif table == 'church_enrichment':
            # Enrichment is 1:1 (791K rows, all distinct church_ids)
            # But no unique constraint, so re-pointing creates duplicates
            # We need to merge enrichment data

            # For survivors that already have enrichment: merge dupe's enrichment data into survivor's
            survivors_with_enrichment = conn.execute(f'''
                SELECT DISTINCT m.survivor_id
                FROM _gps_dedup_map m
                JOIN {table} t1 ON t1.{church_col} = m.survivor_id
                JOIN {table} t2 ON t2.{church_col} = m.dupe_id
            ''').fetchall()
            survivor_ids_with = set(s[0] for s in survivors_with_enrichment)

            merged_count = 0
            if survivor_ids_with:
                # For survivors with existing enrichment, merge dupe's enrichment data
                enrichment_cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()
                                   if r[1] not in ('id', church_col)]

                for sid in survivor_ids_with:
                    # Get dupe enrichment rows for this survivor
                    dupe_rows = conn.execute(f'''
                        SELECT t2.* FROM {table} t2
                        JOIN _gps_dedup_map m ON t2.{church_col} = m.dupe_id
                        WHERE m.survivor_id = ?
                    ''', (sid,)).fetchall()
                    dupe_cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]

                    # Get survivor enrichment row
                    survivor_row = conn.execute(
                        f'SELECT * FROM {table} WHERE {church_col} = ?', (sid,)
                    ).fetchone()

                    if not survivor_row or not dupe_rows:
                        continue

                    survivor_data = dict(zip(dupe_cols, survivor_row))

                    # For each dupe, fill NULLs on survivor
                    updates = {}
                    for dupe_row in dupe_rows:
                        dupe_data = dict(zip(dupe_cols, dupe_row))
                        for col in enrichment_cols:
                            if survivor_data.get(col) is None and dupe_data.get(col) is not None:
                                updates[col] = dupe_data[col]
                                survivor_data[col] = dupe_data[col]

                    if updates:
                        set_clause = ', '.join(f'"{c}" = ?' for c in updates)
                        val = list(updates.values()) + [sid]
                        conn.execute(
                            f'UPDATE {table} SET {set_clause} WHERE {church_col} = ?',
                            val
                        )
                        merged_count += 1

                # Now re-point enrichment rows from dupes that DON'T conflict
                # (survivor didn't have one)
                conn.execute(f'''
                    UPDATE {table} SET {church_col} = (
                        SELECT survivor_id FROM _gps_dedup_map
                        WHERE dupe_id = {table}.{church_col}
                    )
                    WHERE {church_col} IN (
                        SELECT m.dupe_id FROM _gps_dedup_map m
                        LEFT JOIN {table} t1 ON t1.{church_col} = m.survivor_id
                        WHERE t1.{church_col} IS NULL
                    )
                ''')

                # Delete enrichment rows that still point to dupes (where survivor already had one)
                conn.execute(f'''
                    DELETE FROM {table}
                    WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
                    AND {church_col} NOT IN (
                        SELECT m.dupe_id FROM _gps_dedup_map m
                        LEFT JOIN {table} t1 ON t1.{church_col} = m.survivor_id
                        WHERE t1.{church_col} IS NULL
                    )
                ''')
            else:
                # No conflicts - just re-point all
                conn.execute(f'''
                    UPDATE {table} SET {church_col} = (
                        SELECT survivor_id FROM _gps_dedup_map
                        WHERE dupe_id = {table}.{church_col}
                    )
                    WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
                ''')

            conn.commit()
            results[table] = {'action': 'merged', 'rows': merged_count, 'elapsed': time.time() - t0}

        else:
            # Generic OTO handling: just re-point
            conn.execute(f'''
                UPDATE {table} SET {church_col} = (
                    SELECT survivor_id FROM _gps_dedup_map
                    WHERE dupe_id = {table}.{church_col}
                )
                WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
            ''')
            conn.commit()
            results[table] = {'action': 'repoint', 'rows': 0, 'elapsed': time.time() - t0}

    return results


def repoint_mto_child_tables(conn):
    """Re-point many-to-one child tables."""
    results = {}
    for table, church_col, is_oto, priority in CHILD_TABLES:
        if is_oto:
            continue
        t0 = time.time()
        conn.execute(f'''
            UPDATE {table} SET {church_col} = (
                SELECT survivor_id FROM _gps_dedup_map
                WHERE dupe_id = {table}.{church_col}
            )
            WHERE {church_col} IN (SELECT dupe_id FROM _gps_dedup_map)
        ''')
        conn.commit()
        results[table] = {'elapsed': time.time() - t0}
    return results


def main():
    conn = get_conn()
    ensure_temp_table(conn)

    started_at = datetime.now()
    print(f'GPS Dedup started at {started_at.isoformat()}')

    # Check if already partially done
    existing = conn.execute('SELECT COUNT(*) FROM _gps_dedup_map').fetchone()[0]
    if existing > 0:
        print(f'Resuming: {existing} dedup map entries already exist.')
    else:
        print('Fresh run: building dedup map from scratch.')

    # ─── Phase 1: Build dedup map ──────────────────────────────────────────
    offset = existing // 1  # if resuming, need to figure out where we are
    total_processed_groups = 0
    total_dedup_entries = existing

    if existing == 0:
        print('Phase 1: Identifying GPS duplicate groups and selecting survivors...')
        t_start = time.time()
        batch_num = 0

        while True:
            dedup_map = compute_scores_and_groups(
                conn, offset=offset, limit=BATCH_SIZE
            )
            total_groups = count_gps_groups(conn)
            if not dedup_map:
                break

            insert_dedup_map(conn, dedup_map)
            total_dedup_entries += len(dedup_map)
            total_processed_groups += len(set(d['group_id'] for d in dedup_map))
            offset += BATCH_SIZE
            batch_num += 1

            elapsed = time.time() - t_start
            print(f'  Batch {batch_num}: {len(dedup_map)} entries, '
                  f'{total_processed_groups}/{total_groups} groups processed, '
                  f'{elapsed:.1f}s elapsed')

            if total_processed_groups >= total_groups:
                break

        print(f'Phase 1 complete: {total_dedup_entries} dedup entries, '
              f'{total_processed_groups} groups in {time.time()-t_start:.1f}s')

    # Get stats
    total_groups = conn.execute(
        'SELECT COUNT(DISTINCT group_id) FROM _gps_dedup_map'
    ).fetchone()[0]
    total_dupes = conn.execute(
        'SELECT COUNT(*) FROM _gps_dedup_map'
    ).fetchone()[0]
    print(f'\nDedup map: {total_groups} groups, {total_dupes} duplicate records')

    # ─── Phase 2: Handle 1:1 child tables ──────────────────────────────────
    print('\nPhase 2: Handling 1:1 child tables (merge/re-point)...')
    t_start = time.time()
    oto_results = handle_oto_child_tables(conn)
    for table, result in oto_results.items():
        print(f'  {table}: {result["action"]} ({result["elapsed"]:.2f}s)')
    print(f'Phase 2 complete in {time.time()-t_start:.1f}s')

    # ─── Phase 3: Handle M:N child tables ──────────────────────────────────
    print('\nPhase 3: Re-pointing many-to-one child tables...')
    t_start = time.time()
    mto_results = repoint_mto_child_tables(conn)
    for table, result in mto_results.items():
        print(f'  {table}: {result["elapsed"]:.2f}s')
    print(f'Phase 3 complete in {time.time()-t_start:.1f}s')

    # ─── Phase 4: Merge data from dupes into survivors ─────────────────────
    print('\nPhase 4: Merging data from dupes into survivors...')
    t_start = time.time()
    updated, elapsed = merge_columns(conn)
    print(f'  Columns merged: {updated} cells updated in {elapsed:.2f}s')
    src_updated, src_elapsed = merge_source_field(conn)
    print(f'  Source field merged: {src_updated} records in {src_elapsed:.2f}s')
    print(f'Phase 4 complete in {time.time()-t_start:.1f}s')

    # ─── Phase 5: Delete duplicates ────────────────────────────────────────
    print('\nPhase 5: Deleting duplicate records...')
    t_start = time.time()
    deleted, elapsed = delete_dupes(conn)
    print(f'  Deleted {deleted} duplicate records in {elapsed:.2f}s')

    # ─── Phase 6: Log provenance ──────────────────────────── started_at=started_at
    t_start = time.time()
    prov_elapsed = log_provenance(conn, total_groups, deleted,
                                  started_at=datetime.now().isoformat())
    print(f'  Provenance logged in {prov_elapstarted_at

    # ─── Summary ────────────────────────────────────────────────────────────
    final_count = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    print(f'\n{"="*60}')
    print(f'GPS Dedup Complete')
    print(f'{"="*60}')
    print(f'  Groups processed:     {total_groups:,}')
    print(f'  Records deleted:      {deleted:,}')
    print(f'  Churches before:      {final_count + deleted:,}')
    print(f'  Churches after:       {final_count:,}')
    print(f'  Dedup map entries:    {total_dupes:,}')
    print(f'{ "="*60}')

    conn.close()


if __name__ == '__main__':
    main()

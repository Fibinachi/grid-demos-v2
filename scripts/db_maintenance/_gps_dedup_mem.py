"""
GPS-based deduplication — in-memory scoring + targeted SQL writes.

Phase 1 (in-memory): Load churches into pandas, score by non-null count,
                     pick survivor per GPS group, build dedup map.
Phase 2 (SQL):       Merge church columns (fill NULLs on survivor).
Phase 3 (SQL):       Re-point child tables, handle 1:1 merges.
Phase 4 (SQL):       Delete duplicate church records.
Phase 5:             Log provenance.
"""

import sqlite3
import pandas as pd
import time
from datetime import datetime, timezone

# Columns to merge from dupes into survivors
MERGE_COLS = [
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

# 1:1 child tables that need merge logic
OTO_TABLES = ['church_enrichment', 'church_contacts']
# Many-to-one child tables that just need repointing
MTO_TABLES = [
    'church_classification_meta', 'church_broadband',
    'church_sources', 'enrichment_change_log',
]


DB = r'E:\grid\churches.db'

def get_conn():
    conn = sqlite3.connect(DB, timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')
    conn.execute('PRAGMA temp_store=MEMORY')
    return conn


def build_dedup_map(conn):
    """
    Load churches into pandas, score by non-null count, pick survivor per GPS group.
    Creates `_gps_dedup_map` temp table with (group_id, survivor_id, dupe_id).
    """
    print('\n[Phase 1] Loading churches into memory & building dedup map...')
    t0 = time.time()

    score_cols = [r[1] for r in conn.execute('PRAGMA table_info(churches)').fetchall()
                  if r[1] not in ('id', 'latitude', 'longitude')]

    df = pd.read_sql(
        'SELECT id, latitude, longitude, '
        + ', '.join(f'"{c}"' for c in score_cols)
        + ' FROM churches',
        conn
    )
    print(f'  Loaded {len(df):,} rows x {len(df.columns)} cols in {time.time()-t0:.1f}s')

    # Ensure id is numeric (pandas may load INT PK as float)
    df['id'] = pd.to_numeric(df['id'], errors='coerce').fillna(0).astype(int)

    no_gps = df['latitude'].isna() | df['longitude'].isna()
    valid = ~no_gps
    print(f'  Records without GPS: {no_gps.sum():,}')

    # GPS group key at 5dp
    df['_gps_key'] = None
    df.loc[valid, '_gps_key'] = (
        df.loc[valid, 'latitude'].round(5).astype(str)
        + ',' + df.loc[valid, 'longitude'].round(5).astype(str)
    )

    group_sizes = df.loc[valid, '_gps_key'].value_counts()
    dup_groups = group_sizes[group_sizes > 1]
    print(f'  GPS groups: {len(group_sizes):,} total, {len(dup_groups):,} with dupes')

    if len(dup_groups) == 0:
        return {'groups': 0, 'dupes': 0}

    # Score by non-null count
    score_mask_cols = [c for c in score_cols if c != 'id']
    df['_score'] = df[score_mask_cols].notna().sum(axis=1)

    # Vectorized: sort by GPS key + score, pick first per group as survivor
    valid_df = df[valid].copy()
    valid_df.sort_values(['_gps_key', '_score'], ascending=[True, False], inplace=True)
    valid_df.reset_index(drop=True, inplace=True)

    # First entry per GPS key = survivor
    is_first = ~valid_df['_gps_key'].duplicated(keep='first')
    group_ids = is_first.cumsum() - 1  # 0-indexed group IDs

    # Propagate survivor IDs forward within each group (ffill on sorted DataFrame)
    survivor_ids = valid_df['id'].where(is_first).ffill().astype(int)

    # Build dedup entries for non-first rows (the dupes)
    dupe_mask = ~is_first
    dedup_entries = list(zip(
        group_ids[dupe_mask].tolist(),
        survivor_ids[dupe_mask].tolist(),
        valid_df.loc[dupe_mask, 'id'].tolist()
    ))

    n_groups = int(is_first.sum())
    n_dup_groups = len(set(e[0] for e in dedup_entries))
    print(f'  Vectorized: {n_groups:,} total groups ({n_dup_groups:,} with dupes), {len(dedup_entries):,} dupe records')

    # Store dedup map in a temp table
    conn.execute('DROP TABLE IF EXISTS _gps_dedup_map')
    conn.execute('''
        CREATE TABLE _gps_dedup_map (
            group_id    INTEGER,
            survivor_id INTEGER,
            dupe_id     INTEGER
        )
    ''')
    conn.executemany(
        'INSERT INTO _gps_dedup_map VALUES (?, ?, ?)',
        dedup_entries
    )
    conn.execute('CREATE INDEX idx_dedup_dupe ON _gps_dedup_map(dupe_id)')
    conn.execute('CREATE INDEX idx_dedup_survivor ON _gps_dedup_map(survivor_id)')
    conn.commit()

    print(f'  Phase 1 complete in {time.time()-t0:.1f}s')
    return {'groups': n_dup_groups, 'dupes': len(dedup_entries)}


def merge_church_columns(conn):
    """
    Phase 2: Fill NULLs on survivor rows from their dupes.
    Uses pandas to compute merged values, then batch-updates via SQL.
    """
    print('\n[Phase 2] Merging church column data...')
    t0 = time.time()

    # Load survivors and dupes via JOIN queries (avoids huge IN-lists)
    cols_str = ', '.join(f'c."{c}"' for c in MERGE_COLS)
    surv_df = pd.read_sql(
        f'SELECT DISTINCT c.id, {cols_str} FROM churches c '
        'JOIN _gps_dedup_map m ON m.survivor_id = c.id',
        conn
    ).set_index('id')
    surv_df.index = surv_df.index.astype(int)
    surv_df = surv_df[~surv_df.index.duplicated(keep='first')]

    # Load dupes with their survivor mapping
    dupes = pd.read_sql(
        'SELECT m.dupe_id AS id, m.survivor_id FROM _gps_dedup_map m', conn
    )
    dupe_ids = dupes['id'].tolist()

    # Load dupe rows in batches to avoid too-large queries
    dupe_df_parts = []
    batch_size = 50000
    cols_str2 = ', '.join(f'"{c}"' for c in ['id'] + MERGE_COLS)
    for i in range(0, len(dupe_ids), batch_size):
        batch = dupe_ids[i:i+batch_size]
        ids_str = ','.join(str(d) for d in batch)
        part = pd.read_sql(
            f'SELECT {cols_str2} FROM churches WHERE id IN ({ids_str})', conn
        )
        dupe_df_parts.append(part)
    dupe_df = pd.concat(dupe_df_parts, ignore_index=True).set_index('id')
    dupe_df.index = dupe_df.index.astype(int)
    dupe_df = dupe_df[~dupe_df.index.duplicated(keep='first')]

    print(f'  Loaded {len(surv_df):,} survivor rows, {len(dupe_df):,} dupe rows')

    # Pre-group dupes by survivor_id for O(1) lookup (use int keys)
    dupes_by_survivor = {
        int(k): [int(x) for x in v]
        for k, v in dupes.groupby('survivor_id')['id'].apply(list).items()
    }
    n_groups = len(dupes_by_survivor)

    # Debug: check key overlap
    surv_id_set = set(surv_df.index)
    dupe_surv_keys = set(dupes_by_survivor.keys())
    overlap = surv_id_set & dupe_surv_keys
    print(f'  Survivors in surv_df: {len(surv_id_set):,}, in dupes_by_survivor: {len(dupe_surv_keys):,}, overlap: {len(overlap):,}')

    # For each survivor, fill NULL columns from first dupe with value
    updates = {}  # {id: {col: val, ...}}
    for idx, (sid, dupe_id_list) in enumerate(dupes_by_survivor.items()):
        if sid not in surv_df.index:
            continue

        # .loc may return DataFrame if index is non-unique; handle both
        surv_row = surv_df.loc[sid]
        if isinstance(surv_row, pd.DataFrame):
            surv_row = surv_row.iloc[0]

        null_mask = surv_row.isna()
        null_cols = surv_row.index[null_mask].tolist()
        if not null_cols:
            continue

        for col in null_cols:
            for did in dupe_id_list:
                if did not in dupe_df.index:
                    continue
                val = dupe_df.loc[did, col]
                # Safely handle scalar vs Series return (non-unique index)
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.notna(val):
                    updates.setdefault(sid, {})[col] = val
                    break

        if idx > 0 and idx % (max(1, n_groups // 20)) == 0:
            done = sum(len(c) for c in updates.values())
            print(f'    {idx * 100 // n_groups}% ({done:,} cells found)')

    total_cells = sum(len(cols) for cols in updates.values())
    print(f'  Computed {total_cells:,} cells to update across {len(updates):,} survivors')

    # Batch: group by column and do single UPDATE
    col_updates = {c: {} for c in MERGE_COLS}
    for sid, cols in updates.items():
        for col, val in cols.items():
            col_updates[col][sid] = val

    batch_count = 0
    for col, vals in col_updates.items():
        if not vals:
            continue
        # Use CASE for batch update
        case_parts = []
        id_list = []
        for sid, val in vals.items():
            # Escape single quotes in value
            safe_val = str(val).replace("'", "''")
            case_parts.append(f'WHEN {sid} THEN \'{safe_val}\'')
            id_list.append(str(sid))

        if case_parts:
            case_stmt = f'CASE id {" ".join(case_parts)} END'
            ids_str = ','.join(id_list)
            conn.execute(
                f'UPDATE churches SET "{col}" = {case_stmt} WHERE id IN ({ids_str})'
            )
            batch_count += 1
            if batch_count % 10 == 0:
                conn.commit()

    conn.commit()
    print(f'  {batch_count} columns batch-updated, {total_cells:,} cells merged')

    # Merge source field (always do this)
    survivor_sources = conn.execute('''
        SELECT survivor_id, GROUP_CONCAT(source, '|')
        FROM (
            SELECT DISTINCT m.survivor_id, d.source
            FROM _gps_dedup_map m
            JOIN churches d ON d.id = m.dupe_id
            WHERE d.source IS NOT NULL AND d.source != ''
        )
        GROUP BY survivor_id
    ''').fetchall()

    src_updated = 0
    for survivor_id, dupe_sources in survivor_sources:
        current = conn.execute(
            'SELECT source FROM churches WHERE id = ?', (survivor_id,)
        ).fetchone()
        existing = set()
        if current and current[0]:
            existing = set(current[0].split('|'))
        new_parts = [s for s in dupe_sources.split('|') if s and s not in existing]
        if new_parts:
            merged = '|'.join(sorted(existing | set(new_parts)))
            conn.execute('UPDATE churches SET source = ? WHERE id = ?', (merged, survivor_id))
            src_updated += 1

    conn.commit()
    print(f'  {total_cells:,} cells merged, {src_updated} source fields merged')
    print(f'  Phase 2 complete in {time.time()-t0:.1f}s')


def repoint_mto_tables(conn):
    """Phase 3a: Re-point many-to-one child tables (simple repoint)."""
    print('\n[Phase 3a] Re-pointing many-to-one child tables...')
    for table in MTO_TABLES:
        t0 = time.time()
        refs = conn.execute(
            f'SELECT COUNT(*) FROM {table} '
            f'WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)'
        ).fetchone()[0]
        if refs == 0:
            print(f'  {table}: no references ({time.time()-t0:.2f}s)')
            continue
        conn.execute(f'''
            UPDATE {table} SET church_id = (
                SELECT survivor_id FROM _gps_dedup_map WHERE dupe_id = {table}.church_id
            )
            WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)
        ''')
        conn.commit()
        print(f'  {table}: {refs:,} rows ({(time.time()-t0):.2f}s)')


def merge_oto_tables(conn):
    """Phase 3b: Handle 1:1 child tables — merge + delete dupe rows."""
    print('\n[Phase 3b] Handling 1:1 child tables (merge + repoint)...')
    for table in OTO_TABLES:
        t0 = time.time()

        # Re-point rows where survivor does NOT already have a row
        conn.execute(f'''
            UPDATE {table} SET church_id = (
                SELECT survivor_id FROM _gps_dedup_map WHERE dupe_id = {table}.church_id
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

        if conflict_pairs:
            data_cols = [
                r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()
                if r[1] not in ('id', 'church_id')
            ]
            merged = 0

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
            dupe_ids = tuple(set(p[1] for p in conflict_pairs))
            if len(dupe_ids) == 1:
                conn.execute(
                    f'DELETE FROM {table} WHERE church_id = ?', (dupe_ids[0],)
                )
            else:
                conn.execute(
                    f'DELETE FROM {table} WHERE church_id IN ({",".join(str(d) for d in dupe_ids)})'
                )
            conn.commit()
            print(f'  {table}: {repointed} repointed, {merged} merged, {len(conflict_pairs)} deleted')
        else:
            print(f'  {table}: {repointed} repointed, no conflicts')

        print(f'    ({(time.time()-t0):.2f}s)')


def delete_dupes(conn):
    """Phase 4: Delete duplicate church records."""
    print('\n[Phase 4] Deleting duplicate records...')
    t0 = time.time()
    total = 0
    while True:
        conn.execute('''
            DELETE FROM churches WHERE id IN (
                SELECT dupe_id FROM _gps_dedup_map LIMIT 50000
            )
        ''')
        deleted = conn.execute('SELECT changes()').fetchone()[0]
        conn.commit()
        total += deleted
        if deleted == 0:
            break
        print(f'  Deleted {total:,}...')
    print(f'  {total:,} deleted in {time.time()-t0:.1f}s')
    return total


def main():
    started_at = datetime.now(timezone.utc)
    print(f'{"="*60}')
    print(f'GPS Dedup — In-Memory Scoring + Targeted SQL')
    print(f'{"="*60}')
    print(f'Started: {started_at.isoformat()}')

    conn = get_conn()
    conn.execute('DROP TABLE IF EXISTS _gps_dedup_map')
    conn.commit()

    stats = build_dedup_map(conn)
    if stats['dupes'] == 0:
        print('\nNo duplicates found.')
        conn.close()
        return

    merge_church_columns(conn)
    repoint_mto_tables(conn)
    merge_oto_tables(conn)
    deleted = delete_dupes(conn)

    # Log provenance
    notes = (f'GPS dedup at 5dp. '
             f'{deleted:,} duplicates merged into {stats["groups"]:,} survivors. '
             f'Columns merged: {len(MERGE_COLS)}, '
             f'OTO tables: {",".join(OTO_TABLES)}, '
             f'MTO tables: {",".join(MTO_TABLES)}')

    conn.execute('''
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at,
             churches_updated, records_attempted, records_matched,
             status, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
    ''', (
        'gps_dedup', '_gps_dedup_mem.py',
        started_at.isoformat(), datetime.now(timezone.utc).isoformat(),
        deleted, deleted, stats['groups'], notes
    ))
    conn.commit()
    print('  Provenance logged.')

    final = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    print(f'\n{"="*60}')
    print(f'GPS Dedup Complete')
    print(f'{"="*60}')
    print(f'  Groups:     {stats["groups"]:,}')
    print(f'  Deleted:    {deleted:,}')
    print(f'  After:      {final:,}')
    print(f'  Elapsed:    {elapsed:.0f}s')
    print(f'{"="*60}')

    conn.execute('DROP TABLE IF EXISTS _gps_dedup_map')
    conn.commit()
    conn.close()


if __name__ == '__main__':
    main()

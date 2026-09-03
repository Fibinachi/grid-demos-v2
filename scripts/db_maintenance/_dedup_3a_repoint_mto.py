"""
Phase 3a: Re-point many-to-one child tables — in-memory with tqdm progress.

Loads each MTO table into pandas, joins against dedup map,
updates church_id in batches with visible progress bars.
"""
import sqlite3
import pandas as pd
from tqdm import tqdm
import time

DB = r'E:\grid\churches.db'

MTO_TABLES = {
    'church_classification_meta': 'church_id',
    'church_broadband': 'church_id',
    'church_sources': 'church_id',
    'enrichment_change_log': 'church_id',
}

def get_conn():
    conn = sqlite3.connect(DB, timeout=120)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')
    return conn

def main():
    t_start = time.time()
    print(f'{"="*60}')
    print(f'  Phase 3a - Re-point MTO Tables')
    print(f'{"="*60}')

    conn = get_conn()

    # --- Verify dedup map ---
    map_cnt = conn.execute('SELECT COUNT(*) FROM _gps_dedup_map').fetchone()[0]
    print(f'\nDedup map: {map_cnt:,} rows')

    # --- Load dedup map into memory ---
    print('Loading dedup map...', end=' ', flush=True)
    t0 = time.time()
    dedup = pd.read_sql('SELECT dupe_id, survivor_id FROM _gps_dedup_map', conn)
    dedup['dupe_id'] = dedup['dupe_id'].astype(int)
    dedup['survivor_id'] = dedup['survivor_id'].astype(int)
    print(f'{len(dedup):,} rows ({time.time()-t0:.1f}s)')

    # Dict for fast lookup
    dupe_to_survivor = dict(zip(dedup['dupe_id'], dedup['survivor_id']))
    del dedup  # free memory

    for table, fk_col in MTO_TABLES.items():
        print(f'\n--- {table} ---')
        t0 = time.time()

        # Count rows pointing to dupes
        affected = conn.execute(
            f'SELECT COUNT(*) FROM {table} WHERE {fk_col} IN (SELECT dupe_id FROM _gps_dedup_map)'
        ).fetchone()[0]

        if affected == 0:
            print(f'  No rows to repoint (0s)')
            continue

        print(f'  {affected:,} rows to repoint')

        # Load affected rows into pandas (use rowid which is always non-null)
        print(f'  Loading into memory...', end=' ', flush=True)
        df = pd.read_sql(
            f'SELECT rowid AS _pk, {fk_col} FROM {table} WHERE {fk_col} IN (SELECT dupe_id FROM _gps_dedup_map)',
            conn
        )
        # Drop any rows with NULL _pk, then convert
        df = df.dropna(subset=['_pk'])
        df['_pk'] = df['_pk'].astype(int)
        df[fk_col] = pd.to_numeric(df[fk_col], errors='coerce').dropna().astype(int)
        # Re-query to get rows with valid fk_col mapping
        df = df[df[fk_col].notna()].copy()
        df['_pk'] = df['_pk'].astype(int)
        df[fk_col] = df[fk_col].astype(int)
        print(f'{len(df):,} rows ({time.time()-t0:.1f}s)')

        # Map to new church_id using dict
        df['new_id'] = df[fk_col].map(dupe_to_survivor)
        df = df[df['new_id'].notna() & (df['new_id'] != df[fk_col])]
        df['new_id'] = df['new_id'].astype(int)

        if len(df) == 0:
            print(f'  No rows to update')
            continue

        # Update in batches with tqdm
        BATCH_SIZE = 30000
        updated_total = 0

        with tqdm(total=len(df), desc=f'  Updating {table}', unit='rows', smoothing=0) as pbar:
            for i in range(0, len(df), BATCH_SIZE):
                chunk = df.iloc[i:i + BATCH_SIZE]
                # Use CASE-based batch UPDATE on PK
                when_parts = []
                id_list = []
                for _, row in chunk.iterrows():
                    when_parts.append(f'WHEN {int(row["_pk"])} THEN {int(row["new_id"])}')
                    id_list.append(str(int(row['_pk'])))
                if when_parts:
                    case_stmt = f'CASE rowid {" ".join(when_parts)} END'
                    ids_str = ','.join(id_list)
                    conn.execute(
                        f'UPDATE {table} SET {fk_col} = {case_stmt} WHERE rowid IN ({ids_str})'
                    )
                    conn.commit()
                    updated_total += len(chunk)
                    pbar.update(len(chunk))

        elapsed = time.time() - t0
        print(f'  [OK] {updated_total:,} rows repointed ({elapsed:.1f}s)')

    conn.close()
    total_elapsed = time.time() - t_start
    print(f'\n{"="*60}')
    print(f'  Phase 3a complete - {total_elapsed:.1f}s total')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

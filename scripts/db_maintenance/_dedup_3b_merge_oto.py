"""
Phase 3b: Merge 1:1 child tables — in-memory with tqdm progress.

For each OTO table, for each distinct ultimate survivor:
  1. Collect all dupes (from map) that actually have rows in this table
  2. If survivor has a row: merge dupe NULLs into it, then delete dupe rows
  3. If survivor has NO row: repoint first dupe row to survivor,
     merge other dupe rows into it, then delete other dupe rows

Uses CLEAN dedup map: no dupe_id=0, no self-refs, deduplicated.
"""
import sqlite3
from tqdm import tqdm
from collections import defaultdict
import time

DB = r'E:\grid\churches.db'
OTO_TABLES = ['church_enrichment', 'church_contacts']
EXCLUDE_COLS = {'id', 'church_id'}


def get_conn():
    conn = sqlite3.connect(DB, timeout=120)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')
    return conn


def get_table_columns(conn, table):
    rows = conn.execute(f'PRAGMA table_info({table})').fetchall()
    return [r[1] for r in rows if r[1] not in EXCLUDE_COLS]


def load_clean_dedup_map(conn):
    """Load dedup map, excluding dupe_id=0 and self-refs, deduplicating per dupe_id."""
    rows = conn.execute(
        'SELECT dupe_id, survivor_id FROM _gps_dedup_map '
        'WHERE dupe_id != 0 AND dupe_id != survivor_id'
    ).fetchall()
    parent = {}
    for d, s in rows:
        if d not in parent:
            parent[d] = s
    return parent


def build_ultimate_cache(parent):
    """Resolve all chains to ultimate survivors. Returns {dupe_id: ultimate_survivor_id}."""
    parent_set = set(parent.keys())
    resolve = {}
    for did in parent:
        if did in resolve:
            continue
        path = []
        cur = did
        while cur in parent_set:
            if cur in resolve:
                cur = resolve[cur]
                break
            path.append(cur)
            nxt = parent[cur]
            if nxt is None or nxt == cur or nxt not in parent_set:
                # Terminal: nxt is a real survivor
                if nxt is not None:
                    cur = nxt
                break
            cur = nxt
        for node in path:
            resolve[node] = cur
    return resolve


def main():
    t_start = time.time()
    print('=' * 60)
    print('  Phase 3b — Merge OTO Tables')
    print('=' * 60)

    conn = get_conn()

    # Load clean dedup map + resolve chains
    print('\nLoading dedup map...', end=' ', flush=True)
    t0 = time.time()
    parent = load_clean_dedup_map(conn)
    resolve = build_ultimate_cache(parent)
    all_dupe_ids = list(resolve.keys())
    print(f'{len(parent):,} entries, {len(resolve):,} resolved ({time.time()-t0:.1f}s)')

    for table in OTO_TABLES:
        print(f'\n--- {table} ---')
        t0 = time.time()

        # Step A: Find which dupes actually have rows (batched query)
        BATCH = 900
        dupes_with_rows = set()
        for i in range(0, len(all_dupe_ids), BATCH):
            batch = all_dupe_ids[i:i + BATCH]
            ph = ','.join('?' for _ in batch)
            for r in conn.execute(
                f'SELECT DISTINCT church_id FROM {table} WHERE church_id IN ({ph})', batch
            ).fetchall():
                dupes_with_rows.add(r[0])
        if not dupes_with_rows:
            print('  No dupe rows to process')
            continue

        # Build ultimate_survivor -> [list of dupes with rows]
        surv_groups = defaultdict(set)
        for did in dupes_with_rows:
            us = resolve[did]
            surv_groups[us].add(did)

        data_cols = get_table_columns(conn, table)
        total_dupes = sum(len(d) for d in surv_groups.values())
        print(f'  {len(surv_groups):,} groups, {total_dupes:,} dupe rows, '
              f'{len(data_cols):,} data cols ({time.time()-t0:.1f}s)')

        # Step B: Process each group
        repoint_count = 0
        merge_count = 0
        delete_count = 0

        conn.execute('BEGIN')
        cur = conn.cursor()

        for surv_id, dupe_ids in tqdm(surv_groups.items(), desc='  Groups', unit='grp'):
            # Check survivor row
            surv_row = cur.execute(
                f'SELECT {",".join(data_cols)} FROM {table} WHERE church_id = ?', (surv_id,)
            ).fetchone()

            # Filter to dupes that actually have rows
            valid_dupes = []
            dupe_row_data = {}
            for did in dupe_ids:
                dr = cur.execute(
                    f'SELECT {",".join(data_cols)} FROM {table} WHERE church_id = ?', (did,)
                ).fetchone()
                if dr is not None:
                    valid_dupes.append(did)
                    dupe_row_data[did] = dr

            if not valid_dupes:
                continue

            if surv_row is not None:
                # --- Survivor HAS a row: merge dupes into it ---
                # Build merge updates for survivor
                updates = {}
                for did in valid_dupes:
                    dr = dupe_row_data[did]
                    for i, col in enumerate(data_cols):
                        if surv_row[i] is None and dr[i] is not None and col not in updates:
                            updates[col] = dr[i]
                if updates:
                    for col, val in updates.items():
                        cur.execute(f'UPDATE {table} SET "{col}" = ? WHERE church_id = ?',
                                    (val, surv_id))
                    merge_count += 1
                # Delete all dupe rows
                for did in valid_dupes:
                    cur.execute(f'DELETE FROM {table} WHERE church_id = ?', (did,))
                    delete_count += 1
            else:
                # --- Survivor has NO row: repoint first dupe, merge others into it ---
                first_did = valid_dupes[0]
                first_row = dupe_row_data[first_did]
                other_dupes = valid_dupes[1:]

                # Merge values from other dupes into first dupe's row
                target_updates = {}
                for did in other_dupes:
                    dr = dupe_row_data[did]
                    for i, col in enumerate(data_cols):
                        if first_row[i] is None and dr[i] is not None and col not in target_updates:
                            target_updates[col] = dr[i]
                if target_updates:
                    for col, val in target_updates.items():
                        # Update on first_did (pre-repoint)
                        cur.execute(f'UPDATE {table} SET "{col}" = ? WHERE church_id = ?',
                                    (val, first_did))

                # Repoint first dupe to survivor
                cur.execute(
                    f'UPDATE {table} SET church_id = ? WHERE church_id = ?', (surv_id, first_did)
                )
                repoint_count += 1

                # Delete remaining dupe rows
                for did in other_dupes:
                    cur.execute(f'DELETE FROM {table} WHERE church_id = ?', (did,))
                    delete_count += 1

        conn.commit()

        elapsed = time.time() - t0
        print(f'  {repoint_count:,} repointed, {merge_count:,} merged, '
              f'{delete_count:,} dupe rows deleted ({elapsed:.1f}s)')

        # Verify (batched)
        remaining = 0
        for i in range(0, len(all_dupe_ids), BATCH):
            batch = all_dupe_ids[i:i + BATCH]
            ph = ','.join('?' for _ in batch)
            remaining += conn.execute(
                f'SELECT COUNT(*) FROM {table} WHERE church_id IN ({ph})', batch
            ).fetchone()[0]
        print(f'  Remaining dupe refs: {remaining:,}')

    conn.close()
    total_elapsed = time.time() - t_start
    print(f'\n{"=" * 60}')
    print(f'  Phase 3b complete — {total_elapsed:.1f}s total')
    print(f'{"=" * 60}')


if __name__ == '__main__':
    main()

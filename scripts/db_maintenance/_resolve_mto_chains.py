"""
Resolve daisy chains in MTO child tables using path compression + executemany.
Usage: python _resolve_mto_chains.py
"""
import sqlite3, time, sys

DB = r'E:\grid\churches.db'
TABLES = [
    ('church_classification_meta', 'rowid'),
    ('church_broadband', 'rowid'),
    ('church_sources', 'rowid'),
    ('enrichment_change_log', 'rowid'),
]

def main():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    conn.execute('PRAGMA synchronous = OFF')
    conn.execute('PRAGMA journal_mode = WAL')

    # Step 1: Load dedup map
    print('Step 1: Loading dedup map...', end=' ')
    rows = cur.execute('SELECT dupe_id, survivor_id FROM _gps_dedup_map').fetchall()
    parent = {d: s for d, s in rows}
    n_cross = sum(1 for s in parent.values() if s in parent)
    print(f'{len(parent):,} pairs, {n_cross:,} cross-refs ({time.time()-t0:.1f}s)')

    # Step 2: Build ultimate_survivor cache with memoization
    print('Step 2: Resolving chains...', end=' ')
    t1 = time.time()
    # First, find all terminal survivors (not in parent as keys)
    terminals = set()
    for s in parent.values():
        if s not in parent:
            terminals.add(s)
    print(f'{len(terminals):,} terminal survivors', end=' ')

    # Build ultimate cache: for each dupe, walk the chain until we hit a terminal or a cached value
    ultimate_cache = {}
    for did in list(parent.keys()):
        if did in ultimate_cache:
            continue
        if did == parent[did]:
            # Self-reference: dupe == survivor, no repointing needed
            ultimate_cache[did] = did
            continue
        path = []
        current = did
        _safety = 0
        while current in parent:
            _safety += 1
            if _safety > 1000000:
                print(f'  SAFETY: broke infinite loop at {did} -> ... -> {current}')
                ultimate_cache[current] = current
                break
            if current == parent[current]:
                # Self-reference encountered mid-chain
                ultimate_cache[current] = current
                current = current
                break
            path.append(current)
            current = parent[current]
        # current is now the ultimate survivor (or a cached value)
        ultimate = current
        for node in path:
            ultimate_cache[node] = ultimate
    print(f'({time.time()-t1:.1f}s)')

    # Note: max chain depth can't easily be computed without O(n^2) walk
    # The cache resolution above handles all chain depths efficiently

    # Step 3: Process each table
    for tbl, pk in TABLES:
        print(f'\n--- {tbl} ---')
        t2 = time.time()

        # Count affected rows first
        n = cur.execute(f'SELECT COUNT(*) FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
        if n == 0:
            print(f'  No rows to update')
            continue

        # Load affected rows
        cur.execute(f'SELECT {pk} AS _pk, church_id FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)')
        affected = cur.fetchall()
        print(f'  {len(affected):,} rows to check', end=' ', flush=True)

        # Build update list: (new_church_id, pk) for rows that need changing
        updates = []
        for rid, cid in affected:
            new_cid = ultimate_cache.get(cid, cid)
            if new_cid != cid:
                updates.append((new_cid, rid))

        if not updates:
            print('- all already at ultimate')
            continue

        print(f'({len(updates):,} need update)', end=' ', flush=True)

        # Execute batch update
        conn.execute('BEGIN')
        cur.executemany(f'UPDATE {tbl} SET church_id = ? WHERE {pk} = ?', updates)
        conn.commit()
        print(f'-> {len(updates):,} updated ({time.time()-t2:.1f}s)')

    # Step 4: Verify
    print()
    for tbl, _ in TABLES:
        n = cur.execute(f'SELECT COUNT(*) FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
        print(f'  {tbl}: {n:,} remaining')

    conn.close()
    print(f'\nTotal: {time.time()-t0:.1f}s')

if __name__ == '__main__':
    main()

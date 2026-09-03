"""
Fix MTO table daisy chains: resolve all chains to ultimate survivors in memory.
Uses temp table + executemany for fast bulk updates.
Usage: python _fix_mto_chains.py
"""
import sqlite3, time, sys

DB = r'E:\grid\churches.db'
BATCH = 50000

def build_ultimate_map(cur):
    """Build dupe_id -> ultimate_survivor dict with path compression (near-linear)."""
    t0 = time.time()
    rows = cur.execute('SELECT dupe_id, survivor_id FROM _gps_dedup_map').fetchall()
    parent = {d: s for d, s in rows}
    n_cross = sum(1 for s in parent.values() if s in parent)
    print(f'  Dedup map: {len(parent):,} pairs, {n_cross:,} cross-refs ({time.time()-t0:.1f}s)')

    # Path compression: find ultimate survivor for each dupe
    def find(start):
        path = []
        did = start
        steps = 0
        while did in parent:
            path.append(did)
            did = parent[did]
            steps += 1
            if steps > 500000:  # safety: cycles cannot exist in clean dedup map
                print('  WARNING: possible cycle detected, breaking')
                return start
        ultimate = did
        for node in path:
            parent[node] = ultimate
        return ultimate

    for did in list(parent.keys()):
        find(did)  # compresses as side effect

    # Now parent map is dupe_id -> ultimate_survivor
    max_depth = 0
    for did, ult in parent.items():
        d = 0
        s = ult
        while s in parent and d < 1000:
            d += 1
            s = parent[s]
        if d > max_depth:
            max_depth = d

    print(f'  Ultimate map built ({time.time()-t0:.1f}s)')
    return parent

def process_table(conn, cur, tbl, pk, ultimate_map):
    """Process one MTO table: bulk repoint using temp table + executemany."""
    t0 = time.time()
    n = cur.execute(f'SELECT COUNT(*) FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
    if n == 0:
        print(f'  {tbl}: No rows to update')
        return

    print(f'  {tbl}: {n:,} rows to update', end=' ')
    sys.stdout.flush()

    # Load all affected rows
    cur.execute(f'SELECT {pk} AS _pk, church_id FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)')
    affected = [(row[0], row[1], ultimate_map.get(row[1], row[1])) for row in cur.fetchall()
                if ultimate_map.get(row[1], row[1]) != row[1]]

    if not affected:
        print('[all already at ultimate]')
        return

    print(f'({len(affected):,} need change)', end=' ')
    sys.stdout.flush()

    # Bulk update via executemany
    conn.execute('BEGIN TRANSACTION')
    cur.executemany(
        f'UPDATE {tbl} SET church_id = ? WHERE {pk} = ?',
        [(new, rid) for rid, old, new in affected]
    )
    conn.commit()
    print(f'-> OK ({time.time()-t0:.1f}s)')

def main():
    t0 = time.time()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    ultimate_map = build_ultimate_map(cur)

    tables = [
        ('church_classification_meta', 'rowid'),
        ('church_broadband', 'rowid'),
        ('church_sources', 'rowid'),
        ('enrichment_change_log', 'rowid'),
    ]

    for tbl, pk in tables:
        process_table(conn, cur, tbl, pk, ultimate_map)

    # Verify
    print()
    for tbl, _ in tables:
        n = cur.execute(f'SELECT COUNT(*) FROM {tbl} WHERE church_id IN (SELECT dupe_id FROM _gps_dedup_map)').fetchone()[0]
        print(f'  {tbl}: {n:,} remaining')

    conn.close()
    print(f'\nTotal: {time.time()-t0:.1f}s')

if __name__ == '__main__':
    main()

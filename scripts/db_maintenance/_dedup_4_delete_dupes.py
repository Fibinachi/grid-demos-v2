"""
Phase 4: Delete duplicate church records — in-memory with tqdm progress.

Loads dupe IDs from dedup map, deletes in batches with visible progress bar.
"""
import sqlite3
from tqdm import tqdm
import time
from datetime import datetime, timezone

DB = r'E:\grid\churches.db'

def get_conn():
    conn = sqlite3.connect(DB, timeout=120)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    conn.execute('PRAGMA cache_size=-800000')
    return conn

def main():
    t_start = time.time()
    print(f'{"="*60}')
    print(f'  Phase 4 — Delete Duplicate Church Records')
    print(f'{"="*60}')

    conn = get_conn()

    # Count churches before
    before = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    print(f'\nChurches before: {before:,}')

    # Load dupe IDs — EXCLUDE self-refs (survivors!) and dupe_id=0 (garbage)
    t0 = time.time()
    dupe_ids = [r[0] for r in conn.execute(
        'SELECT DISTINCT dupe_id FROM _gps_dedup_map '
        'WHERE dupe_id != 0 AND dupe_id != survivor_id'
    ).fetchall()]
    print(f'Dupe IDs to delete: {len(dupe_ids):,} ({time.time()-t0:.1f}s to load)')

    if not dupe_ids:
        print('Nothing to delete.')
        conn.close()
        return

    # Delete in batches with tqdm
    BATCH_SIZE = 50000
    total_deleted = 0

    with tqdm(total=len(dupe_ids), desc='  Deleting dupes', unit='rows', smoothing=0) as pbar:
        for i in range(0, len(dupe_ids), BATCH_SIZE):
            batch = dupe_ids[i:i + BATCH_SIZE]
            ids_str = ','.join(str(d) for d in batch)
            conn.execute(f'DELETE FROM churches WHERE id IN ({ids_str})')
            conn.commit()
            total_deleted += len(batch)
            pbar.update(len(batch))

    # Count churches after
    after = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    elapsed = time.time() - t_start

    print(f'\n  ✅ {total_deleted:,} duplicate records deleted ({elapsed:.1f}s)')
    print(f'  Churches: {before:,} → {after:,} ({before - after:,} removed)')

    conn.close()
    print(f'\n{"="*60}')
    print(f'  Phase 4 complete')
    print(f'{"="*60}')

if __name__ == '__main__':
    main()

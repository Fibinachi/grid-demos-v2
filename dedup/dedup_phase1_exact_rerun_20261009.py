"""GRID dedup Phase 1 — mechanical exact-match re-run, 2026-10-09.

Merges unmerged rows sharing (normalized_name, GPS@4dp), with the >=10
shared-coordinate guard (centroid collisions are NOT dupes).

Phases: --phase backup | merge | verify | all
Soft-merge only: losers keep status='merged' + dedup_canonical_id pointer.
Survivor = most non-null columns (tie: lowest id); survivor NULLs filled
from losers; church_addresses repointed; provenance logged.
Rollback: _dedup_phase1_backup_20261009 (full churches rows) +
          _dedup_phase1_addr_backup_20261009 (address_id, church_id).
"""
import argparse, sqlite3, sys, time
from datetime import datetime

DB = r'E:/grid/churches.db'
BACKUP = '_dedup_phase1_backup_20261009'
ADDR_BACKUP = '_dedup_phase1_addr_backup_20261009'
SKIP_COLS = {'id', 'status', 'dedup_canonical_id', 'normalized_name'}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def candidate_groups(con):
    """Return list of id-lists, guarded."""
    log("computing hot coordinates (>=10 rows sharing rounded GPS)...")
    hot = set()
    for la, lo in con.execute(
            """SELECT ROUND(latitude,4), ROUND(longitude,4) FROM churches
               WHERE latitude IS NOT NULL AND longitude IS NOT NULL
               GROUP BY 1, 2 HAVING COUNT(*) >= 10"""):
        hot.add((la, lo))
    log(f"hot coordinates: {len(hot)}")
    groups = []
    skipped = 0
    cur = con.execute("""SELECT GROUP_CONCAT(id), normalized_name,
                                ROUND(latitude,4), ROUND(longitude,4)
                         FROM churches
                         WHERE status IS NULL AND normalized_name != ''
                           AND latitude IS NOT NULL AND longitude IS NOT NULL
                         GROUP BY normalized_name, ROUND(latitude,4), ROUND(longitude,4)
                         HAVING COUNT(*) > 1""")
    for ids_str, nm, la, lo in cur:
        if (la, lo) in hot:
            skipped += 1
            continue
        groups.append([int(i) for i in ids_str.split(',')])
    log(f"candidate groups={len(groups)} skipped_by_guard={skipped}")
    return groups


def nonnull_count(row, cols):
    return sum(1 for c in cols if row[c] is not None)


def phase_backup(con, groups):
    ids = sorted({i for g in groups for i in g})
    for tbl in (BACKUP, ADDR_BACKUP):
        if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                       (tbl,)).fetchone():
            log(f"{tbl} exists, skipping backup")
            return ids
    t0 = time.time()
    con.execute(f"CREATE TABLE {BACKUP} AS SELECT * FROM churches WHERE 0")
    con.execute(f"""INSERT INTO {BACKUP} SELECT * FROM churches
                    WHERE id IN ({','.join('?'*len(ids))})""", ids)
    con.execute(f"""CREATE TABLE {ADDR_BACKUP} AS
                    SELECT address_id, church_id FROM church_addresses
                    WHERE church_id IN ({','.join('?'*len(ids))})""", ids)
    con.commit()
    n = con.execute(f"SELECT COUNT(*) FROM {BACKUP}").fetchone()[0]
    na = con.execute(f"SELECT COUNT(*) FROM {ADDR_BACKUP}").fetchone()[0]
    log(f"backup: {n} church rows, {na} address rows ({time.time()-t0:.1f}s)")
    return ids


def phase_merge(con, groups):
    cols = [r[1] for r in con.execute("PRAGMA table_info(churches)")]
    fill_cols = [c for c in cols if c not in SKIP_COLS]
    merged_total = 0
    t0 = time.time()
    for gi, ids in enumerate(groups):
        rows = [dict(zip(cols, r)) for r in con.execute(
            f"SELECT * FROM churches WHERE id IN ({','.join('?'*len(ids))})", ids)]
        # re-check unmerged (defensive)
        rows = [r for r in rows if r['status'] is None]
        if len(rows) < 2:
            continue
        rows.sort(key=lambda r: (-nonnull_count(r, cols), r['id']))
        surv = rows[0]
        losers = rows[1:]
        # fill survivor NULLs
        updates = {}
        for c in fill_cols:
            if surv[c] is None:
                for l in losers:
                    if l[c] is not None:
                        updates[c] = l[c]
                        break
        if updates:
            con.execute(
                f"UPDATE churches SET {','.join(c+'=?' for c in updates)} WHERE id=?",
                list(updates.values()) + [surv['id']])
        # repoint addresses + mark losers
        for l in losers:
            con.execute("UPDATE church_addresses SET church_id=? WHERE church_id=?",
                        (surv['id'], l['id']))
            con.execute("UPDATE churches SET status='merged', dedup_canonical_id=? WHERE id=?",
                        (surv['id'], l['id']))
            merged_total += 1
        if (gi + 1) % 200 == 0:
            con.commit()
            log(f"  {gi+1}/{len(groups)} groups, {merged_total} merged")
    con.execute(
        """INSERT INTO provenance_log (source, script_name, started_at, completed_at,
           churches_updated, status, notes) VALUES (?,?,?,?,?,?,?)""",
        ("dedup", "dedup_phase1_exact_rerun_20261009",
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
         merged_total, "completed",
         "Phase 1 exact normalized_name+GPS@4dp re-run, >=10 shared-coord guard. "
         "Rollback tables: _dedup_phase1_backup_20261009, _dedup_phase1_addr_backup_20261009."))
    con.commit()
    log(f"merge done: {merged_total} rows merged in {len(groups)} groups "
        f"({time.time()-t0:.1f}s)")


def phase_verify(con):
    m = con.execute("SELECT COUNT(*) FROM churches WHERE status='merged'").fetchone()[0]
    # remaining candidate groups should be 0 (excluding guard-skipped)
    groups = candidate_groups(con)
    print(f"VERIFY merged_total={m:,} remaining_groups={len(groups)}")
    # spot check: no loser points to a merged row
    bad = con.execute("""SELECT COUNT(*) FROM churches m JOIN churches c
                         ON m.dedup_canonical_id=c.id
                         WHERE m.status='merged' AND c.status='merged'""").fetchone()[0]
    print(f"VERIFY chained={bad}")
    assert len(groups) == 0 and bad == 0, "VERIFY FAILED"
    print("VERIFY OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', default='all', choices=('backup', 'merge', 'verify', 'all'))
    args = ap.parse_args()
    con = sqlite3.connect(DB, timeout=120)
    try:
        groups = candidate_groups(con)
        if args.phase in ('backup', 'all'):
            phase_backup(con, groups)
        if args.phase in ('merge', 'all'):
            phase_merge(con, groups)
        if args.phase in ('verify', 'all'):
            phase_verify(con)
    finally:
        con.close()


if __name__ == '__main__':
    main()

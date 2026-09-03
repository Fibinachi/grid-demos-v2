"""
Delete partial-match state-only records from scraper sources.

These are state-only records (null GPS, US, state-only) that:
  1. Have a partial name match with a GPS-having record in the same state
  2. Come from crawler/scraper sources (catholic_diocese_scrape, diocese_sitemap)

Confirmed by _analyze_partial_source.py: these sources produce garbage
(job postings, event flyers, page artifacts) rather than real church records.

Usage:
  python _delete_scraper_garbage_partial.py          # dry run
  python _delete_scraper_garbage_partial.py --apply  # for real
"""
import sqlite3
import time
import shutil
import sys
from collections import defaultdict

DB = 'E:/grid/churches.db'
GARBAGE_SOURCES = ('catholic_diocese_scrape', 'diocese_sitemap')

# Tables with NO ACTION FK — must delete manually before church record
NO_CASCADE_TABLES = [
    'church_enrichment', 'church_contacts', 'church_operations',
    'church_broadcast', 'church_arda', 'attendance_history',
    'church_census_us', 'church_food_desert', 'church_vacancies',
    'church_census_ca', 'church_census_mx',
]


def progress_bar(current, total, start_time, extra=""):
    cols = shutil.get_terminal_size().columns - 20
    bar_w = max(10, cols - 40)
    pct = current / total if total else 0
    filled = int(bar_w * pct)
    bar = '█' * filled + '░' * (bar_w - filled)
    elapsed = time.time() - start_time
    rate = current / elapsed if elapsed > 0 and current > 0 else 0
    if rate > 0 and current < total:
        eta = (total - current) / rate
        eta_str = f"{eta:.0f}s"
    else:
        eta_str = "done"
    print(f"\r  {current:>7,}/{total:<7,} [{bar}] {pct:>5.1f}% | {rate:>,.0f} rec/s | ETA {eta_str} {extra}", end='', flush=True)


def main():
    APPLY = '--apply' in sys.argv
    if APPLY:
        print("🔴 LIVE MODE — changes WILL be written to database")
        confirm = input("  Type 'yes' to confirm: ")
        if confirm != 'yes':
            print("  Aborted.")
            return
    else:
        print("🟡 DRY RUN — no changes written. Use --apply to run for real.")
        print()

    t0 = time.time()
    db = sqlite3.connect(DB)
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=OFF")  # We'll handle child tables manually

    # ── 1. Load state-only records from scraper sources ──
    print("Loading state-only records from scraper sources...")
    so_records = db.execute("""
        SELECT rowid, id,
               COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
               name AS raw_name, state, source
        FROM churches
        WHERE latitude IS NULL AND longitude IS NULL
        AND country = 'US' AND state IS NOT NULL AND state != ''
        AND (city IS NULL OR city = '')
        AND (zip IS NULL OR zip = '')
        AND (address IS NULL OR address = '')
        AND source IN ('catholic_diocese_scrape', 'diocese_sitemap')
        ORDER BY rowid
    """).fetchall()
    print(f"  State-only scraper records: {len(so_records):,}")

    # ── 2. Load GPS-having records (for partial match detection) ──
    print("Loading GPS-having records...")
    gps_records = db.execute("""
        SELECT rowid, id,
               COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
               state
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        AND country = 'US' AND state IS NOT NULL AND state != ''
        AND name IS NOT NULL AND name != ''
        ORDER BY rowid
    """).fetchall()
    print(f"  GPS-having records: {len(gps_records):,}")

    # ── 3. Build GPS index ──
    print("Building GPS name index...")
    idx = defaultdict(lambda: defaultdict(list))
    t_idx = time.time()
    for i, r in enumerate(gps_records):
        st, nm = r[3], r[2]
        if nm:
            idx[st][nm.strip().lower()].append(r)
        progress_bar(i + 1, len(gps_records), t_idx, "| building index")
    print()

    # ── 4. Find which state-only records are partial matches ──
    print("Identifying partial matches...")
    to_delete = []  # (so_rowid, so_id, so_name, state, source)
    for i, so in enumerate(so_records):
        so_rid, so_id, so_sname, so_raw, so_state, so_src = so
        so_key = so_sname.strip().lower() if so_sname else ''

        if not so_key:
            continue

        matches = idx.get(so_state, {})
        is_partial = False

        for gps_key in matches:
            if (gps_key.startswith(so_key) and len(gps_key) > len(so_key)) or \
               (so_key.startswith(gps_key) and len(so_key) > len(gps_key)):
                is_partial = True
                break

        if is_partial:
            to_delete.append(so)

        progress_bar(i + 1, len(so_records), t_idx, f"| to_delete:{len(to_delete)}")
    print()

    print(f"\n  Partial matches to delete: {len(to_delete):,}")

    if not to_delete:
        print("  Nothing to do!")
        db.close()
        return

    # ── 5. Collect IDs for deletion ──
    all_ids = [r[1] for r in to_delete]  # church.id values
    id_str = ','.join(str(x) for x in all_ids)

    # ── 6. Dry run: just show counts ──
    if not APPLY:
        print(f"\n{'─'*60}")
        print("DRY RUN SUMMARY")
        print(f"{'─'*60}")

        # Count child records
        total_child = 0
        for tname in NO_CASCADE_TABLES:
            cols = [c[1] for c in db.execute(f'PRAGMA table_info("{tname}")')]
            if 'church_id' in cols:
                cnt = db.execute(f'SELECT COUNT(*) FROM "{tname}" WHERE church_id IN ({id_str})').fetchone()[0]
                if cnt:
                    total_child += cnt
                    print(f"  Will delete {cnt:>8,} rows from {tname}")

        # Also check CASCADE tables (just log)
        cascade_tables = ['broadcast_ministries', 'church_broadband',
                          'church_classification_meta', 'church_fcc', 'church_gnis',
                          'church_metro_area', 'church_nrhp', 'church_postal_admin',
                          'jw_hierarchy']
        for tname in cascade_tables:
            cols = [c[1] for c in db.execute(f'PRAGMA table_info("{tname}")')]
            if 'church_id' in cols:
                cnt = db.execute(f'SELECT COUNT(*) FROM "{tname}" WHERE church_id IN ({id_str})').fetchone()[0]
                if cnt:
                    print(f"  Will cascade-delete {cnt:>8,} rows from {tname}")

        total_child += db.execute(f'SELECT COUNT(*) FROM church_sources WHERE church_id IN ({id_str})').fetchone()[0]
        print(f"  Will delete {total_child:>8,} child rows total")
        print(f"  Will delete {len(to_delete):>8,} church records")
        print(f"\n{'─'*60}")
        print("🟡 Dry run complete. Use --apply to execute.")
        print(f"{'─'*60}")
        db.close()
        return

    # ── 7. LIVE: Delete child records (NO CASCADE tables) ──
    CHUNK_SIZE = 500
    print(f"\n{'─'*60}")
    print("LIVE — deleting child records...")
    print(f"{'─'*60}")

    total_deleted = 0
    for tname in NO_CASCADE_TABLES:
        cols = [c[1] for c in db.execute(f'PRAGMA table_info("{tname}")')]
        if 'church_id' not in cols:
            continue
        # Delete in chunks
        ids = list(all_ids)
        for chunk_start in range(0, len(ids), CHUNK_SIZE):
            chunk = ids[chunk_start:chunk_start + CHUNK_SIZE]
            chunk_str = ','.join(str(x) for x in chunk)
            db.execute(f'DELETE FROM "{tname}" WHERE church_id IN ({chunk_str})')
        cnt = db.execute(f'SELECT changes()').fetchone()[0]
        if cnt:
            print(f"  Deleted {cnt:,} rows from {tname}")
            total_deleted += cnt

    # church_sources (has church_id)
    for chunk_start in range(0, len(all_ids), CHUNK_SIZE):
        chunk = all_ids[chunk_start:chunk_start + CHUNK_SIZE]
        chunk_str = ','.join(str(x) for x in chunk)
        db.execute(f'DELETE FROM church_sources WHERE church_id IN ({chunk_str})')
    cnt = db.execute(f'SELECT changes()').fetchone()[0]
    if cnt:
        print(f"  Deleted {cnt:,} rows from church_sources")
        total_deleted += cnt

    # church_territories (has church_id)
    for chunk_start in range(0, len(all_ids), CHUNK_SIZE):
        chunk = all_ids[chunk_start:chunk_start + CHUNK_SIZE]
        chunk_str = ','.join(str(x) for x in chunk)
        db.execute(f'DELETE FROM church_territories WHERE church_id IN ({chunk_str})')
    cnt = db.execute(f'SELECT changes()').fetchone()[0]
    if cnt:
        print(f"  Deleted {cnt:,} rows from church_territories")
        total_deleted += cnt

    print(f"  Total child records deleted: {total_deleted:,}")

    # ── 8. LIVE: Delete church records ──
    print(f"\n{'─'*60}")
    print("LIVE — deleting church records...")
    print(f"{'─'*60}")

    t_del = time.time()
    for i, so in enumerate(to_delete):
        so_rid, so_id, so_sname, so_raw, so_state, so_src = so
        db.execute('DELETE FROM churches WHERE rowid=?', (so_rid,))
        progress_bar(i + 1, len(to_delete), t_del, f"| deleting")
    print()

    # ── 9. Log provenance ──
    print("\nLogging provenance...")
    from collections import Counter
    src_counter = Counter()
    for so in to_delete:
        src_counter[so[5]] += 1

    for src, cnt in src_counter.most_common():
        print(f"  Deleted {cnt:,} from source: {src}")
        db.execute("""
            INSERT INTO provenance_log (church_id, source, action, timestamp, details)
            VALUES (?, ?, 'deleted', datetime('now'), ?)
        """, (
            f"batch_{src}_{int(time.time())}",
            src, f"Batch delete of {cnt} state-only partial-match records from {src}"
        ))

    db.commit()
    elapsed = time.time() - t0
    print(f"\n{'─'*60}")
    print(f"✅ DONE — Deleted {len(to_delete):,} garbage records in {elapsed:.1f}s")
    print(f"{'─'*60}")
    db.close()


if __name__ == '__main__':
    main()

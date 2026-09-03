"""
Merge exact-match state-only records into their GPS-having counterparts.

For each state-only record (null GPS, US, state-only) that has an exact
name+state match with a GPS-having record:
  1. Copy any non-null fields from state-only record into GPS record
  2. Delete the state-only record
  3. Log provenance

Usage:
  python _merge_exact_dupes.py          # dry run
  python _merge_exact_dupes.py --apply  # for real
"""
import sqlite3
import time
import shutil
import json
import sys

DB = 'E:/grid/churches.db'

# Columns we'll attempt to merge (all except identifiers/keys)
MERGE_COLUMNS = [
    'denomination', 'family', 'faith', 'faith_tradition', 'tradition_legacy',
    'subtradition', 'religion_type', 'normalized_name',
    'address', 'city', 'state', 'zip', 'zip5', 'zip4',
    'ein', 'ntee_code', 'latitude', 'longitude', 'geocode_source', 'fips',
    'source', 'denomination_affiliation', 'address_source', 'holy_site_id',
    'landmark_type', 'is_landmark', 'heritage_status',
    'height_m', 'width_m', 'length_m', 'area_m2', 'capacity', 'building_year',
    'source_primary', 'source_secondary',
    'confidence_score',
    'cra_bn', 'cra_category', 'cra_sub_category', 'cra_designation',
    'mosque_type', 'canonical_status', 'heritage_source', 'dedication',
    'muslim_affiliation', 'muslim_confidence', 'muslim_classification_source', 'muslim_updated',
    'name_original', 'age_centuries',
    'county', 'county_fips_5', 'name_transliterated',
    'continent', 'region_un', 'subregion',
]

# Never merge these — they're unique identifiers or system fields
SKIP_COLUMNS = {'id', 'rowid', 'osm_id', 'osm_type', 'osm_version', 'osm_timestamp',
                'wikidata_qid', 'wikidata_last_modified', 'overture_id'}


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

    t0 = time.time()
    db = sqlite3.connect(DB)
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA journal_mode=WAL")

    # ── 1. Load state-only records ──
    print("\nLoading state-only records...")
    state_only = db.execute("""
        SELECT rowid, id, name, COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
               state
        FROM churches
        WHERE latitude IS NULL AND longitude IS NULL
        AND country = 'US'
        AND state IS NOT NULL AND state != ''
        AND (city IS NULL OR city = '')
        AND (zip IS NULL OR zip = '')
        AND (address IS NULL OR address = '')
        ORDER BY rowid
    """).fetchall()
    print(f"  State-only records: {len(state_only):,}")

    # ── 2. Load GPS-having records ──
    print("Loading GPS-having records...")
    gps_records = db.execute("""
        SELECT rowid, id,
               COALESCE(NULLIF(TRIM(name_transliterated),''), name) AS search_name,
               state
        FROM churches
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        AND country = 'US'
        AND state IS NOT NULL AND state != ''
        AND name IS NOT NULL AND name != ''
        ORDER BY rowid
    """).fetchall()
    print(f"  GPS-having records: {len(gps_records):,}")

    # ── 3. Build index ──
    from collections import defaultdict
    state_name_index = defaultdict(lambda: defaultdict(list))
    print("Building index...")
    t_idx = time.time()
    for i, r in enumerate(gps_records):
        st = r[3]
        nm = r[2]
        if nm:
            key = nm.strip().lower()
            state_name_index[st][key].append(r)
        progress_bar(i + 1, len(gps_records), t_idx, "| building index")
    print()

    # ── 4. Find exact matches and build merge list ──
    print("\nFinding exact matches...")
    merges = []  # (so_rowid, so_id, gps_rowid, gps_id, state, name)
    t_match = time.time()
    for i, so in enumerate(state_only):
        so_rowid, so_id, so_raw_name, so_sname, so_state = so
        so_key = so_sname.strip().lower() if so_sname else ''

        if not so_key:
            continue

        matches = state_name_index.get(so_state, {})
        if so_key in matches:
            for gps_r in matches[so_key]:
                merges.append((so_rowid, so_id, gps_r[0], gps_r[1], so_state, so_raw_name))

        progress_bar(i + 1, len(state_only), t_match, f"| found {len(merges)} merges")
    print()

    # Deduplicate: one state-only record might match multiple GPS records
    # We'll pick the first GPS match (lowest rowid = earliest inserted)
    seen_so = set()
    deduped = []
    for m in merges:
        if m[0] not in seen_so:
            seen_so.add(m[0])
            deduped.append(m)
    merges = deduped

    print(f"\n  Exact matches to merge: {len(merges):,}")

    if not merges:
        print("  Nothing to do!")
        db.close()
        return

    # ── 5. Perform merges ──
    # For each pair, read all columns, merge, delete
    CHUNK_SIZE = 500

    # Get column list once
    all_cols = [c[1] for c in db.execute('PRAGMA table_info(churches)').fetchall()
                if c[1] not in SKIP_COLUMNS]

    def read_record(rowid):
        """Read all mergeable columns for a given rowid."""
        cols_str = ', '.join(f'"{c}"' for c in all_cols)
        row = db.execute(f'SELECT {cols_str} FROM churches WHERE rowid=?', (rowid,)).fetchone()
        return {c: v for c, v in zip(all_cols, row)}

    stats = {
        'merged': 0,
        'with_updates': 0,
        'fields_copied': 0,
        'deleted': 0,
        'errors': 0,
    }
    field_counter = defaultdict(int)  # track which fields get copied most

    print(f"\n{'─'*60}")
    if APPLY:
        print("MERGING...")
    else:
        print("DRY RUN — would merge:")
    print(f"{'─'*60}")

    t_merge = time.time()
    for idx, (so_rid, so_id, gps_rid, gps_id, state, name) in enumerate(merges):
        try:
            # Read both records
            so_data = read_record(so_rid)
            gps_data = read_record(gps_rid)

            # Find columns where state-only has non-null and GPS has null
            updates = {}
            for col in all_cols:
                so_val = so_data[col]
                gps_val = gps_data[col]
                if so_val is not None and gps_val is None:
                    updates[col] = so_val

            if updates:
                stats['with_updates'] += 1
                stats['fields_copied'] += len(updates)
                for col in updates:
                    field_counter[col] += 1

                if APPLY:
                    # Build UPDATE SET
                    set_clause = ', '.join(f'"{c}"=?' for c in updates)
                    vals = list(updates.values()) + [gps_rid]
                    db.execute(f'UPDATE churches SET {set_clause} WHERE rowid=?', vals)

            if APPLY:
                # Delete the inferior state-only record
                # First delete from child tables
                for child_table in ['church_enrichment', 'church_contacts', 'church_addresses',
                                    'church_fcc', 'church_gnis', 'church_nrhp',
                                    'church_metro_area', 'church_broadband',
                                    'church_classification_meta',
                                    'church_postal_admin']:
                    db.execute(f'DELETE FROM {child_table} WHERE church_id=?', (so_id,))

                # Delete from churches
                db.execute('DELETE FROM churches WHERE rowid=?', (so_rid,))

                # Provenance log
                detail = {
                    'action': 'merged_into_gps_record',
                    'deleted_rowid': so_rid,
                    'deleted_id': so_id,
                    'kept_rowid': gps_rid,
                    'kept_id': gps_id,
                    'name': name,
                    'state': state,
                    'fields_copied': list(updates.keys()) if updates else [],
                }
                db.execute(
                    """INSERT INTO provenance_log(church_id, source, action, details)
                       VALUES (?, 'merge_exact_dupes', 'merged', ?)""",
                    (gps_id, json.dumps(detail))
                )
                db.execute(
                    """INSERT INTO provenance_log(church_id, source, action, details)
                       VALUES (?, 'merge_exact_dupes', 'deleted', ?)""",
                    (so_id, json.dumps(detail))
                )

                stats['deleted'] += 1
            else:
                stats['merged'] += 1

            # Periodic commit
            if APPLY and (idx + 1) % CHUNK_SIZE == 0:
                db.commit()

        except Exception as e:
            stats['errors'] += 1
            print(f"\n  ERROR at merge #{idx}: {e}")

        progress_bar(idx + 1, len(merges), t_merge,
                     f"| del:{stats['deleted']} upd:{stats['with_updates']} err:{stats['errors']}")

    if APPLY:
        db.commit()

    print(f"\n\n{'='*60}")
    print("MERGE RESULTS")
    print(f"{'='*60}")
    if APPLY:
        print(f"  Records deleted:          {stats['deleted']:,}")
        print(f"  Records with field copy:  {stats['with_updates']:,}")
        print(f"  Total fields copied:      {stats['fields_copied']:,}")
        print(f"  Errors:                   {stats['errors']:,}")
    else:
        print(f"  Records to delete:        {len(merges):,}")
        print(f"  With field copies needed: {stats['with_updates']:,}")
        print(f"  Total fields to copy:     {stats['fields_copied']:,}")
        print(f"  Errors:                   {stats['errors']:,}")

    if field_counter:
        print(f"\n  Top fields copied from state-only:")
        for col, cnt in sorted(field_counter.items(), key=lambda x: -x[1])[:15]:
            print(f"    {col:.30s}: {cnt:,}")

    db.close()
    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")

    if not APPLY:
        print(f"\n  To execute: python _merge_exact_dupes.py --apply")


if __name__ == '__main__':
    main()

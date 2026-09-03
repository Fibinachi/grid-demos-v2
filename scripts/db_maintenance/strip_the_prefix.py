"""
Strip leading 'The ' / 'THE ' / 'the ' from church names.

Also handles trailing ' The' / ', The' (standalone, not 'of the' or 'in the').

Uses `rowid` instead of `id` because 34K+ records have NULL `id`.

Usage:
    python scripts/db_maintenance/strip_the_prefix.py             # live
    python scripts/db_maintenance/strip_the_prefix.py --dry-run   # preview only
"""

import re, sys, sqlite3
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CHUNK = 500

LEADING_THE_RE = re.compile(r'^the\s+', re.IGNORECASE)
TRAILING_COMMA_THE_RE = re.compile(r',\s*the\s*$', re.IGNORECASE)
TRAILING_THE_RE = re.compile(r'\s+the\s*$', re.IGNORECASE)


def get_db():
    db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def log_enrichment_change(cur, church_id, field_name, old_value, new_value, change_source):
    cur.execute("""
        INSERT INTO enrichment_change_log
            (church_id, field_name, old_value, new_value, change_source, changed_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
    """, (church_id, field_name, old_value, new_value, change_source))


def log_provenance(db, script_name, started_at, churches_updated, notes):
    cur = db.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, 'name', 'completed', ?)
    """, ('strip_the_prefix.py', script_name, started_at, now, churches_updated, notes))
    db.commit()


def progress_bar(current, total, label=''):
    if total == 0:
        return
    pct = current * 100 // total
    bar_len = 40
    filled = pct * bar_len // 100
    bar = chr(9608) * filled + chr(9617) * (bar_len - filled)
    print(f'\r  {label} [{bar}] {pct:3d}% ({current:,}/{total:,})', end='', flush=True)
    if current >= total:
        print()


def strip_leading_the(name):
    m = LEADING_THE_RE.match(name)
    if m:
        stripped = name[m.end():]
        # If the leading word was all-lowercase "the", capitalize first letter of remainder
        if m.group(0).lower() == 'the ' and stripped and stripped[0].islower():
            stripped = stripped[0].upper() + stripped[1:]
        return stripped
    return name


def strip_trailing_the(name):
    m = TRAILING_COMMA_THE_RE.search(name)
    if m:
        return name[:m.start()]
    m = TRAILING_THE_RE.search(name)
    if m:
        preceding = name[:m.start()].rstrip()
        last_word = preceding.rsplit(' ', 1)[-1].lower() if ' ' in preceding else ''
        if last_word not in ('of', 'in', '-', chr(8211)):
            return preceding
    return name


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Strip Leading 'The' Prefix ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    # Phase 1: Leading "The "
    c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE 'The %' OR name LIKE 'THE %' OR name LIKE 'the %'")
    leading_total = c.fetchone()[0]
    print(f"\nPhase 1 - Leading 'The ':  {leading_total:,} candidates", flush=True)

    c.execute("""
        SELECT rowid, id, name FROM churches
        WHERE (name LIKE 'The %' OR name LIKE 'THE %' OR name LIKE 'the %')
        ORDER BY rowid
    """)
    rows = c.fetchall()
    print(f"  Loaded {len(rows):,} rows", flush=True)

    changes = []
    for rowid, ch_id, name in rows:
        new_name = strip_leading_the(name)
        if new_name != name:
            changes.append((new_name, rowid, name))
            if DRY_RUN and len(changes) <= 15:
                print(f"    [rowid={rowid}] {name[:75]} -> {new_name[:75]}", flush=True)

    leading_fixes = len(changes)
    if leading_fixes == 0:
        print("  No leading 'The' to fix.", flush=True)
    elif DRY_RUN:
        print(f"\n  Would fix leading 'The': {leading_fixes:,}", flush=True)
    else:
        applied = 0
        for i in range(0, len(changes), 5000):
            batch = changes[i:i + 5000]
            c.executemany("UPDATE churches SET name=? WHERE rowid=?", [(n, rid) for n, rid, _ in batch])
            applied += len(batch)
            db.commit()
            progress_bar(applied, len(changes), 'Leading The')
        print(f"  Fixed leading 'The': {leading_fixes:,}", flush=True)

    # Phase 2: Trailing " The" / ", The"
    print(f"\nPhase 2 - Trailing ' The' / ', The':", flush=True)

    trailing_where = (
        "(name LIKE '%, The' OR name LIKE '%, THE' "
        "OR (name LIKE '% The' AND name NOT LIKE '% of The' "
        "AND name NOT LIKE '% OF THE' AND name NOT LIKE '% in The' "
        "AND name NOT LIKE '% IN THE' AND name NOT LIKE '%, The' "
        "AND name NOT LIKE '%, THE'))"
    )
    c.execute(f"SELECT rowid, id, name FROM churches WHERE {trailing_where} ORDER BY rowid")
    trailing_rows = c.fetchall()
    print(f"  Candidates: {len(trailing_rows):,}", flush=True)

    trailing_changes = []
    for rowid, ch_id, name in trailing_rows:
        new_name = strip_trailing_the(name)
        if new_name != name:
            trailing_changes.append((new_name, rowid, name))

    if DRY_RUN:
        print(f"  Would fix trailing: {len(trailing_changes):,}", flush=True)
        for new_n, rid, old_n in trailing_changes:
            print(f"    [rowid={rid}] {old_n[:75]} -> {new_n[:75]}", flush=True)
    elif trailing_changes:
        applied2 = 0
        for i in range(0, len(trailing_changes), 5000):
            batch = trailing_changes[i:i + 5000]
            c.executemany("UPDATE churches SET name=? WHERE rowid=?", [(n, rid) for n, rid, _ in batch])
            applied2 += len(batch)
            db.commit()
            progress_bar(applied2, len(trailing_changes), 'Trailing The')
        print(f"  Fixed trailing 'The': {len(trailing_changes):,}", flush=True)

    total_updates = leading_fixes + len(trailing_changes)

    # Phase 3: Logging
    if not DRY_RUN and total_updates > 0:
        print(f"\nLogging enrichment changes ({total_updates:,})...", flush=True)
        all_changes = changes + trailing_changes
        for i in range(0, len(all_changes), CHUNK):
            batch = all_changes[i:i + CHUNK]
            for new_n, rid, old_n in batch:
                log_enrichment_change(c, rid, 'name', old_n, new_n, 'strip_the_prefix')
            db.commit()
            progress_bar(min(i + CHUNK, len(all_changes)), len(all_changes), 'Logging')

        note_parts = [f'Stripped leading "The " from {leading_fixes:,} names']
        if trailing_changes:
            note_parts.append(f'{len(trailing_changes)} trailing fixes')
        log_provenance(db, 'strip_the_prefix.py', started_at, total_updates, '; '.join(note_parts))
        print(f"  Provenance logged.", flush=True)

        # Sync normalized_name
        print(f"\nSyncing normalized_name column...", flush=True)
        c.execute("CREATE TEMP TABLE IF NOT EXISTS _the_fix_rows (rowid INTEGER PRIMARY KEY)")
        c.execute("DELETE FROM _the_fix_rows")
        for i in range(0, len(all_changes), 5000):
            batch_rids = [(rid,) for _, rid, _ in all_changes[i:i + 5000]]
            c.executemany("INSERT OR IGNORE INTO _the_fix_rows (rowid) VALUES (?)", batch_rids)
        db.commit()

        c.execute("""
            UPDATE churches SET normalized_name = name
            WHERE rowid IN (SELECT rowid FROM _the_fix_rows)
        """)
        synced = c.rowcount
        db.commit()
        c.execute("DROP TABLE IF EXISTS _the_fix_rows")
        print(f"  normalized_name synced for {synced:,} records.", flush=True)

    # Summary
    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Leading 'The ' fixed: {leading_fixes:,}", flush=True)
    print(f"  Trailing ' The' fixed: {len(trailing_changes):,}", flush=True)
    print(f"  Total updates: {total_updates:,}", flush=True)
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()

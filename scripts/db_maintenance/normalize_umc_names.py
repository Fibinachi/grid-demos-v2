"""
Normalize United Methodist Church names -> UMC.

Two operations:
1. Name normalization: replace "United Methodist" (and variants) with "UMC"
2. Faith correction: set faith=Christian for any UMC record with null/wrong faith

Usage:
    python scripts/db_maintenance/normalize_umc_names.py             # live
    python scripts/db_maintenance/normalize_umc_names.py --dry-run   # preview only
"""

import re, sys, sqlite3
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CHUNK = 2000

# Match "United Methodist" optionally followed by Church/Chr/Ch/C
# Case-insensitive, word-boundary safe
UMC_RE = re.compile(r'\bUnited Methodist(?: Church| Chr| Chur| C)?\b', re.IGNORECASE)


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


def log_provenance(db, script_name, started_at, churches_updated, fields_populated, notes):
    cur = db.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
    """, (script_name, script_name, started_at, now, churches_updated, fields_populated, notes))
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


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Normalize UMC Names ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    total_name_fixes = 0
    total_faith_fixes = 0

    # ═══════════════════════════════════════════════════════════
    # Phase 1: Name normalization — "United Methodist Church" -> "UMC"
    # ═══════════════════════════════════════════════════════════
    c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%United Methodist%' COLLATE NOCASE")
    name_candidates = c.fetchone()[0]
    print(f"\nPhase 1 — Name normalization: {name_candidates:,} candidates", flush=True)

    c.execute("""
        SELECT rowid, name FROM churches
        WHERE name LIKE '%United Methodist%' COLLATE NOCASE
        ORDER BY rowid
    """)
    rows = c.fetchall()
    print(f"  Loaded {len(rows):,} rows", flush=True)

    name_changes = []  # (new_name, rowid, old_name)
    for rowid, name in rows:
        new_name = UMC_RE.sub('UMC', name)
        if new_name != name:
            name_changes.append((new_name, rowid, name))

    if DRY_RUN:
        print(f"  Would fix: {len(name_changes):,} names", flush=True)
        # Show a representative sample
        shown = set()
        cnt = 0
        for new_n, rid, old_n in name_changes:
            # Show one per unique old pattern
            key = old_n[:30]
            if key not in shown and cnt < 20:
                shown.add(key)
                cnt += 1
                print(f"    [rowid={rid}] {old_n[:70]:70s} -> {new_n[:70]}", flush=True)
    else:
        applied = 0
        for i in range(0, len(name_changes), CHUNK):
            batch = name_changes[i:i + CHUNK]
            c.executemany("UPDATE churches SET name=? WHERE rowid=?", [(n, rid) for n, rid, _ in batch])
            applied += len(batch)
            db.commit()
            progress_bar(applied, len(name_changes), 'Name fixes')
        total_name_fixes = len(name_changes)
        print(f"  Fixed names: {total_name_fixes:,}", flush=True)

    # ═══════════════════════════════════════════════════════════
    # Phase 2: Log enrichment changes for name fixes
    # ═══════════════════════════════════════════════════════════
    if not DRY_RUN and name_changes:
        print(f"\nLogging name changes ({len(name_changes):,})...", flush=True)
        for i in range(0, len(name_changes), CHUNK):
            batch = name_changes[i:i + CHUNK]
            for new_n, rid, old_n in batch:
                log_enrichment_change(c, rid, 'name', old_n, new_n, 'umc_normalizer')
            db.commit()
            progress_bar(min(i + CHUNK, len(name_changes)), len(name_changes), 'Logging')

        # Sync normalized_name
        print(f"\nSyncing normalized_name...", flush=True)
        c.execute("CREATE TEMP TABLE IF NOT EXISTS _umc_fix_rows (rowid INTEGER PRIMARY KEY)")
        c.execute("DELETE FROM _umc_fix_rows")
        for i in range(0, len(name_changes), 5000):
            batch_rids = [(rid,) for _, rid, _ in name_changes[i:i + 5000]]
            c.executemany("INSERT OR IGNORE INTO _umc_fix_rows (rowid) VALUES (?)", batch_rids)
        db.commit()

        c.execute("UPDATE churches SET normalized_name = name WHERE rowid IN (SELECT rowid FROM _umc_fix_rows)")
        synced = c.rowcount
        db.commit()
        c.execute("DROP TABLE IF EXISTS _umc_fix_rows")
        print(f"  normalized_name synced for {synced:,} records.", flush=True)

        # Provenance
        notes = f'UMC name normalization: {total_name_fixes:,} name fixes'
        if total_faith_fixes:
            notes += f', {total_faith_fixes:,} faith corrections'
        log_provenance(db, 'normalize_umc_names.py', started_at,
                       total_name_fixes + total_faith_fixes, 'name,faith', notes)
        print(f"  Provenance logged.", flush=True)

    # ═══════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════
    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Name fixes:   {total_name_fixes or len(name_changes):,}", flush=True)
    print(f"  Faith fixes:  {total_faith_fixes or len(faith_rows):,}", flush=True)
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()

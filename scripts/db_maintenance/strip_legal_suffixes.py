"""
Strip legal entity suffixes from church names.
Handles INC, CORP, LLC, PA, LTD, CO, and common variants.

Usage:
    python scripts/db_maintenance/strip_legal_suffixes.py             # live
    python scripts/db_maintenance/strip_legal_suffixes.py --dry-run   # preview only
"""

import re, sys, sqlite3
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
CHUNK = 5000

# Trailing legal suffix with optional comma/space before
SUFFIX_RE = re.compile(
    r',?\s*(?:INC\.?|CORP\.?|LLC\.?|PC\.?|PA\.?|LTD\.?|CO\.?|INTL|CORPORATION|COMPANY|LIMITED|PARTNERSHIP|ENTERPRISES)\s*$',
    re.IGNORECASE
)


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
    """, (script_name, script_name, started_at, now, churches_updated, notes))
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


def strip_name(name):
    """Remove legal suffixes from a church name. Returns cleaned name or None if no change."""
    orig = name
    new = SUFFIX_RE.sub('', name).strip()
    # Clean up any trailing comma, double spaces
    new = re.sub(r'\s*,?\s*$', '', new)
    new = re.sub(r'\s{2,}', ' ', new)
    return new if new != orig and new else None


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Strip Legal Suffixes ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    # Build WHERE clause from all suffix patterns
    patterns = [
        "% INC", "% INC.", "%, INC", "%, INC.",
        "% CORP", "% CORP.", "%, CORP",
        "% LLC", "% LLC.", "%, LLC", "%, LLC.",
        "% PC", "% PC.",
        "% PA", "% PA.", "%, PA", "%, PA.",
        "% LTD", "% LTD.", "%, LTD",
        "% CO", "% CO.",
        "% INTL",
        "% CORPORATION",
        "% COMPANY",
        "% LIMITED",
        "% PARTNERSHIP",
        "% ENTERPRISES",
    ]
    where_clause = " OR ".join(f"name LIKE '{p}'" for p in patterns)

    c.execute(f"SELECT COUNT(*) FROM churches WHERE {where_clause}")
    total_candidates = c.fetchone()[0]
    print(f"\nCandidates: {total_candidates:,}", flush=True)

    c.execute(f"SELECT rowid, name FROM churches WHERE {where_clause} ORDER BY rowid")
    rows = c.fetchall()
    print(f"Loaded {len(rows):,} rows", flush=True)

    changes = []  # (new_name, rowid, old_name)
    for rowid, name in rows:
        new_name = strip_name(name)
        if new_name:
            changes.append((new_name, rowid, name))

    if DRY_RUN:
        print(f"\nWould fix: {len(changes):,}", flush=True)
        print(f"\nSample (first 20):", flush=True)
        shown = 0
        for new_n, rid, old_n in changes:
            if shown < 20:
                print(f"  [rowid={rid}] {old_n[:70]:70s} -> {new_n[:70]}", flush=True)
                shown += 1
        # Count by suffix
        suffix_counts = {}
        for new_n, rid, old_n in changes:
            upper = old_n.upper()
            for s in ['INC', 'CORP', 'LLC', 'PA', 'PC', 'LTD', 'CO', 'INTL',
                       'CORPORATION', 'COMPANY', 'LIMITED', 'PARTNERSHIP',
                       'ENTERPRISES']:
                if s in upper and old_n.rstrip().endswith(s) or old_n.rstrip().endswith(s + '.'):
                    suffix_counts[s] = suffix_counts.get(s, 0) + 1
                    break
        print(f"\nBy suffix:", flush=True)
        for s, cnt in sorted(suffix_counts.items(), key=lambda x: -x[1]):
            print(f"  {s:15s} {cnt:>8,}", flush=True)
    else:
        applied = 0
        for i in range(0, len(changes), CHUNK):
            batch = changes[i:i + CHUNK]
            c.executemany("UPDATE churches SET name=? WHERE rowid=?", [(n, rid) for n, rid, _ in batch])
            applied += len(batch)
            db.commit()
            progress_bar(applied, len(changes), 'Stripping')
        print(f"  Fixed: {len(changes):,}", flush=True)

        # Log enrichment changes
        print(f"\nLogging changes...", flush=True)
        for i in range(0, len(changes), CHUNK):
            batch = changes[i:i + CHUNK]
            for new_n, rid, old_n in batch:
                log_enrichment_change(c, rid, 'name', old_n, new_n, 'strip_legal_suffixes')
            db.commit()
            progress_bar(min(i + CHUNK, len(changes)), len(changes), 'Logging')

        # Sync normalized_name
        print(f"\nSyncing normalized_name...", flush=True)
        c.execute("CREATE TEMP TABLE IF NOT EXISTS _suffix_rows (rowid INTEGER PRIMARY KEY)")
        c.execute("DELETE FROM _suffix_rows")
        for i in range(0, len(changes), 5000):
            batch_rids = [(rid,) for _, rid, _ in changes[i:i + 5000]]
            c.executemany("INSERT OR IGNORE INTO _suffix_rows (rowid) VALUES (?)", batch_rids)
        db.commit()
        c.execute("UPDATE churches SET normalized_name = name WHERE rowid IN (SELECT rowid FROM _suffix_rows)")
        synced = c.rowcount
        db.commit()
        c.execute("DROP TABLE IF EXISTS _suffix_rows")
        print(f"  normalized_name synced for {synced:,} records.", flush=True)

        # Provenance
        log_provenance(db, 'strip_legal_suffixes.py', started_at, len(changes),
                       f'Stripped legal suffixes from {len(changes):,} records')
        print(f"  Provenance logged.", flush=True)

    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Total: {len(changes):,}", flush=True)
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()

"""
Standardize Names v2 — Fast, raw-sqlite3, no Provenance overhead.
Runs all remaining phases against churches.db.

Usage:
    python scripts/db_maintenance/standardize_names_v2.py [--phase 1|2|3|4] [--dry-run]
"""

import re, sys, os, sqlite3, time
from datetime import datetime

DRY_RUN = '--dry-run' in sys.argv
PHASES = []
for a in sys.argv:
    if a.startswith('--phase='):
        PHASES = [int(a.split('=')[1])]
    elif a == '--phase':
        idx = sys.argv.index(a)
        if idx + 1 < len(sys.argv):
            PHASES = [int(sys.argv[idx + 1])]
if not PHASES:
    PHASES = [1, 2, 3, 4]


def get_db():
    """Raw connection with high timeout."""
    db = sqlite3.connect('E:\\grid\\churches.db', timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def log_change(cur, church_id, old_val, new_val, action):
    """Minimal change logging."""
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
        VALUES (?, 'name_standardizer_v2', ?, ?, ?)
    """, (church_id, action, f'{old_val} => {new_val}', now))


# ═══════════════════════════════════════════════════════════════
# Phase 1: SQL REPLACE for ST. → SAINT, MT. → MOUNT, FT. → FORT
# ═══════════════════════════════════════════════════════════════
def phase1(db):
    c = db.cursor()
    total = 0
    rules = [
        ('ST.', 'SAINT', 'ST. → SAINT'),
        ('MT.', 'MOUNT', 'MT. → MOUNT'),
        ('FT.', 'FORT', 'FT. → FORT'),
    ]
    for old, new, desc in rules:
        c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ?", (f'%{old}%',))
        found = c.fetchone()[0]
        if found == 0:
            print(f"  {desc}: 0 found", flush=True)
            continue
        print(f"  {desc}: {found:,} found", flush=True)
        if not DRY_RUN:
            c.execute("UPDATE churches SET name = REPLACE(name, ?, ?) WHERE name LIKE ?",
                      (old, new, f'%{old}%'))
            total += c.rowcount
            db.commit()
            print(f"    → Updated {c.rowcount:,}", flush=True)
    return total


# ═══════════════════════════════════════════════════════════════
# Phase 2: Word-boundary patterns (ST→SAINT, MT→MOUNT, FT→FORT, CTR→CENTER)
# ═══════════════════════════════════════════════════════════════
PHASE2_PATS = [
    (re.compile(r'\bST(?!REET)\b'), 'SAINT'),
    (re.compile(r'\bCTR\b'), 'CENTER'),
    (re.compile(r'\bMT\b'), 'MOUNT'),
    (re.compile(r'\bFT\b'), 'FORT'),
]

def phase2(db):
    c = db.cursor()
    where = ("(name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%') "
             "OR name LIKE '% CTR %' "
             "OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%') "
             "OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')")
    c.execute(f"SELECT id, name FROM churches WHERE {where}")
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        counts = {}
        for _, name in rows:
            for pat, repl in PHASE2_PATS:
                if pat.search(name):
                    counts[repl] = counts.get(repl, 0) + 1
        for repl, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  → {repl}: {cnt:,}")
        return 0

    updates = []
    total = 0
    counts = {}
    batch_size = 5000

    for cid, name in rows:
        new_name = name
        for pat, repl in PHASE2_PATS:
            if pat.search(new_name):
                new_name = pat.sub(repl, new_name)
                counts[repl] = counts.get(repl, 0) + 1
        if new_name != name:
            updates.append((new_name, cid))

        if len(updates) >= batch_size:
            c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
            total += len(updates)
            updates = []
            db.commit()
            print(f"  Applied {total:,}...", flush=True)

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        total += len(updates)
        db.commit()

    for repl, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {repl}: {cnt:,}")
    print(f"  Total: {total:,}", flush=True)
    return total


# ═══════════════════════════════════════════════════════════════
# Phase 3: Possessive apostrophe
# ═══════════════════════════════════════════════════════════════
POSS_RE = re.compile(r"\b(SAINT\s+\w+)\s+S(?=\s|$)")

def phase3(db):
    c = db.cursor()
    sql_where = ("(name LIKE '% SAINT % S %' OR name LIKE 'SAINT % S %' "
                 "OR name LIKE '% SAINT % S' OR name LIKE 'SAINT % S')")
    c.execute(f"SELECT id, name FROM churches WHERE {sql_where}")
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        for cid, name in rows[:10]:
            m = POSS_RE.search(name)
            if m:
                new_name = POSS_RE.sub(r"\1'S", name)
                print(f"    [{cid}] {name[:70]} → {new_name[:70]}", flush=True)
        return 0

    updates = []
    for cid, name in rows:
        m = POSS_RE.search(name)
        if m:
            new_name = POSS_RE.sub(r"\1'S", name)
            if new_name != name:
                updates.append((new_name, cid))

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        db.commit()
    print(f"  Fixed: {len(updates):,}", flush=True)
    return len(updates)


# ═══════════════════════════════════════════════════════════════
# Phase 4: Strip INC/INC.
# ═══════════════════════════════════════════════════════════════
INC_TRAIL_RE = re.compile(r',?\s*INC\.?\s*$')
INC_MID_RE = re.compile(r',?\s*INC\.?\s+')

def phase4(db):
    c = db.cursor()
    c.execute("SELECT id, name FROM churches WHERE name LIKE '% INC' OR name LIKE '% INC.'")
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        end_inc = sum(1 for _, n in rows if INC_TRAIL_RE.search(n))
        print(f"  End INC: {end_inc:,}, Mid INC: {len(rows)-end_inc:,}")
        shown = 0
        for cid, name in rows:
            new_name = INC_TRAIL_RE.sub('', name)
            new_name = INC_MID_RE.sub(' ', new_name).strip()
            new_name = re.sub(r'\s{2,}', ' ', new_name)
            if new_name and new_name != name:
                shown += 1
                if shown <= 6:
                    print(f"    [{cid}] {name[:70]} → {new_name[:70]}", flush=True)
        return 0

    updates = []
    total = 0
    batch_size = 5000

    for cid, name in rows:
        new_name = INC_TRAIL_RE.sub('', name)
        new_name = INC_MID_RE.sub(' ', new_name).strip()
        new_name = re.sub(r'\s{2,}', ' ', new_name)
        if new_name and new_name != name:
            updates.append((new_name, cid))

        if len(updates) >= batch_size:
            c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
            total += len(updates)
            updates = []
            db.commit()
            print(f"  Applied {total:,}...", flush=True)

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        total += len(updates)
        db.commit()

    print(f"  Total: {total:,}", flush=True)
    return total


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════
def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Name Standardization v2 ({mode}) === Phases: {PHASES}", flush=True)
    db = get_db()
    c = db.cursor()
    total = 0

    if 1 in PHASES:
        print("\n--- Phase 1: SQL REPLACE Abbreviations ---", flush=True)
        total += phase1(db)

    if 2 in PHASES:
        print("\n--- Phase 2: Word-Boundary Patterns ---", flush=True)
        total += phase2(db)

    if 3 in PHASES:
        print("\n--- Phase 3: Possessive Apostrophe ---", flush=True)
        total += phase3(db)

    if 4 in PHASES:
        print("\n--- Phase 4: Strip INC ---", flush=True)
        total += phase4(db)

    # Log via enrichment_change_log
    if not DRY_RUN and total > 0:
        now = datetime.now().isoformat()
        c.execute("""
            INSERT INTO enrichment_change_log (church_id, source, action, details, changed_at)
            VALUES (0, 'name_standardizer_v2', 'batch_standardize', ?, ?)
        """, (f'Standardized {total:,} names across phases {PHASES}', now))
        db.commit()
        print(f"\nLogged {total:,} changes to enrichment_change_log", flush=True)

    # Verification
    if not DRY_RUN:
        print("\n=== Final Counts ===", flush=True)
        checks = [
            ("ST. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST.%'"),
            ("ST (bare, non-street)", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%'"),
            ("SAINT total", "SELECT COUNT(*) FROM churches WHERE name LIKE '% SAINT %' OR name LIKE 'SAINT %'"),
            ("MT. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT.%'"),
            ("FT. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% FT.%'"),
            ("CTR remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% CTR %'"),
            ("MT (bare)", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT %' AND name NOT LIKE '% MT.%'"),
            ("FT (bare)", "SELECT COUNT(*) FROM churches WHERE name LIKE '% FT %' AND name NOT LIKE '% FT.%'"),
            ("INC/INC. remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% INC' OR name LIKE '% INC.'"),
            ("Saint S (possessive uncounted)", "SELECT COUNT(*) FROM churches WHERE (name LIKE '% SAINT % S' OR name LIKE 'SAINT % S') AND name NOT LIKE '% INC' AND name NOT LIKE '% INC.'"),
        ]
        for label, sql in checks:
            c.execute(sql)
            print(f"  {label}: {c.fetchone()[0]:,}", flush=True)

    db.close()
    print(f"\nDone. {total:,} total changes.", flush=True)


if __name__ == '__main__':
    main()

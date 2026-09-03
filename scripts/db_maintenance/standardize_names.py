"""
Standardize Church Name Abbreviations & Cleanup
================================================
Phase 1 — Abbreviation expansion (SQL-level bulk REPLACE):
    ST. → SAINT, MT. → MOUNT, FT. → FORT

Phase 2 — Word-boundary patterns (Python batch):
    ST → SAINT (avoid STREET), MT → MOUNT, FT → FORT, CTR → CENTER

Phase 3 — Possessive apostrophe (SAINT PAUL S → SAINT PAUL'S)
Phase 4 — Strip INC/INC. legal suffix

Uses gw_db for provenance tracking.

Usage:
    python scripts/db_maintenance/standardize_names.py [--phase 1|2|3|4] [--dry-run]
"""

import re
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from gw_db import connect, Provenance

DRY_RUN = '--dry-run' in sys.argv

# Parse which phases to run
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


# ──────────────────────────────────────────────────────────────────────
# Phase 1: Simple punctuation abbreviations → SQL REPLACE (very fast)
# ──────────────────────────────────────────────────────────────────────
# Phase 1: Only patterns with a period are safe for SQL REPLACE (unambiguous).
# Bare MT/FT use word-boundary regex in Phase 2.
PHASE1_RULES = [
    ('ST.', 'SAINT', 'ST. → SAINT'),
    ('MT.', 'MOUNT', 'MT. → MOUNT'),
    ('FT.', 'FORT', 'FT. → FORT'),
]

def run_phase1(db):
    """SQL-level REPLACE for simple abbreviation patterns."""
    c = db.cursor()
    total_fixed = 0
    print("\n=== Phase 1: Abbreviation Expansion (SQL REPLACE) ===", flush=True)

    for old, new, desc in PHASE1_RULES:
        # Count first
        c.execute("SELECT COUNT(*) FROM churches WHERE name LIKE ?", (f'%{old}%',))
        found = c.fetchone()[0]
        if found == 0:
            print(f"  {desc}: 0 found, skipping.", flush=True)
            continue
        print(f"  {desc}: {found:,} candidates", flush=True)

        if DRY_RUN:
            continue

        # Apply REPLACE — works because names are UPPERCASE
        c.execute("UPDATE churches SET name = REPLACE(name, ?, ?) WHERE name LIKE ?",
                  (old, new, f'%{old}%'))
        fixed = c.rowcount
        print(f"    → Updated {fixed:,}", flush=True)
        total_fixed += fixed
        db.commit()

    return total_fixed


# ──────────────────────────────────────────────────────────────────────
# Phase 2: Word-boundary patterns requiring regex (ST vs STREET, CTR)
# ──────────────────────────────────────────────────────────────────────
PHASE2_PATTERNS = [
    (re.compile(r'\bST(?!REET)\b'), 'SAINT', 'ST → SAINT'),
    (re.compile(r'\bCTR\b'), 'CENTER', 'CTR → CENTER'),
    (re.compile(r'\bMT\b'), 'MOUNT', 'MT → MOUNT'),
    (re.compile(r'\bFT\b'), 'FORT', 'FT → FORT'),
]

def run_phase2(db):
    """Python batch for word-boundary patterns."""
    c = db.cursor()
    print("\n=== Phase 2: Word-Boundary Patterns ===", flush=True)

    # Build WHERE clause to find candidates
    where = ("(name LIKE '% ST %' AND name NOT LIKE '% STREET %' "
             "AND name NOT LIKE '% ST.%') "
             "OR name LIKE '% CTR %' "
             "OR (name LIKE '% MT %' AND name NOT LIKE '% MT.%') "
             "OR (name LIKE '% FT %' AND name NOT LIKE '% FT.%')")
    c.execute(f"SELECT id, name FROM churches WHERE {where}")
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        # Just count what would change
        total = 0
        counts = {}
        for _, name in rows:
            for pat, repl, desc in PHASE2_PATTERNS:
                if pat.search(name):
                    counts[desc] = counts.get(desc, 0) + 1
                    total += 1
        for desc, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {desc}: {cnt:,}")
        print(f"  Total to update: {total:,}")
        return total

    # Process in batches
    batch_size = 5000
    updates = []
    total_fixed = 0
    counts = {}

    for church_id, name in rows:
        new_name = name
        for pat, repl, desc in PHASE2_PATTERNS:
            if pat.search(new_name):
                new_name = pat.sub(repl, new_name)
                counts[desc] = counts.get(desc, 0) + 1
        if new_name != name:
            updates.append((new_name, church_id))

        if len(updates) >= batch_size:
            c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
            total_fixed += len(updates)
            updates = []
            db.commit()
            print(f"  Applied {total_fixed:,}...", flush=True)

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        total_fixed += len(updates)
        db.commit()

    for desc, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {desc}: {cnt:,}")
    print(f"  Total updated: {total_fixed:,}", flush=True)
    return total_fixed


# ──────────────────────────────────────────────────────────────────────
# Phase 3: Possessive apostrophe (SAINT PAUL S → SAINT PAUL'S)
# ──────────────────────────────────────────────────────────────────────
def run_phase3(db):
    """Fix possessive-S after saint names: SAINT PAUL S → SAINT PAUL'S"""
    c = db.cursor()
    print("\n=== Phase 3: Possessive Apostrophe ===", flush=True)

    # Pattern: SAINT <WORD> S  (the S is a standalone letter before space or end)
    # Also handle the broader pattern where " S " appears after a saint name
    # Match: "SAINT <name> S " or ending in " SAINT <name> S"
    pat = re.compile(r"\b(SAINT\s+\w+)\s+S(?=\s|$)")
    pat2 = re.compile(r"\b(SAINT\s+\w+'\w+)\s+S(?=\s|$)")  # already has apostrophe — skip

    sql_where = ("(name LIKE '% SAINT % S %' OR name LIKE 'SAINT % S %' "
                 "OR name LIKE '% SAINT % S' OR name LIKE 'SAINT % S')")

    c.execute(f"SELECT id, name FROM churches WHERE {sql_where}")
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        fixed = 0
        for church_id, name in rows:
            m = pat.search(name)
            m2 = pat2.search(name)
            if m and not m2:
                new_name = pat.sub(r"\1'S", name)
                print(f"    [{church_id}] \"{name[:70]}\"")
                print(f"            → \"{new_name[:70]}\"")
                fixed += 1
                if fixed >= 10:
                    break
        print(f"  Would fix: ~{len(rows):,}")
        return 0

    updates = []
    for church_id, name in rows:
        m = pat.search(name)
        m2 = pat2.search(name)
        if m and not m2:
            new_name = pat.sub(r"\1'S", name)
            if new_name != name:
                updates.append((new_name, church_id))

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        db.commit()

    print(f"  Fixed possessive-S: {len(updates):,}", flush=True)
    return len(updates)


# ──────────────────────────────────────────────────────────────────────
# Phase 4: Strip INC/INC. legal suffix
# ──────────────────────────────────────────────────────────────────────
STRIP_INC_RE = re.compile(r',?\s*INC\.?\s*$')
MID_INC_RE = re.compile(r',?\s*INC\.?\s+')

def run_phase4(db):
    """Remove INC/INC. suffixes from church names."""
    c = db.cursor()
    print("\n=== Phase 4: Strip INC/INC. Suffix ===", flush=True)

    # Find all names with INC or INC.
    c.execute("""
        SELECT id, name FROM churches 
        WHERE name LIKE '% INC' OR name LIKE '% INC.'
    """)
    rows = c.fetchall()
    print(f"  Candidates: {len(rows):,}", flush=True)

    if DRY_RUN:
        # Count end vs mid
        end_inc = sum(1 for _, n in rows if STRIP_INC_RE.search(n))
        mid_inc = len(rows) - end_inc
        print(f"  End INC: {end_inc:,}, Mid INC: {mid_inc:,}")
        shown = 0
        for church_id, name in rows:
            new_name = STRIP_INC_RE.sub('', name)
            new_name = MID_INC_RE.sub(' ', new_name).strip()
            new_name = re.sub(r'\s{2,}', ' ', new_name)
            if new_name and new_name != name:
                shown += 1
                if shown <= 8:
                    print(f"    [{church_id}] \"{name[:70]}\"")
                    print(f"            → \"{new_name[:70]}\"")
        return 0

    batch_size = 5000
    updates = []
    total_fixed = 0

    for church_id, name in rows:
        # Strip trailing INC/INC. (including preceding comma+space)
        new_name = STRIP_INC_RE.sub('', name)
        # Strip mid-name INC. (with comma and following space)
        new_name = MID_INC_RE.sub(' ', new_name).strip()
        # Clean up any resulting double spaces
        new_name = re.sub(r'\s{2,}', ' ', new_name)
        if new_name and new_name != name:
            updates.append((new_name, church_id))

        if len(updates) >= batch_size:
            c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
            total_fixed += len(updates)
            updates = []
            db.commit()
            print(f"  Applied {total_fixed:,}...", flush=True)

    if updates:
        c.executemany("UPDATE churches SET name=? WHERE id=?", updates)
        total_fixed += len(updates)
        db.commit()

    print(f"  Total INC stripped: {total_fixed:,}", flush=True)
    return total_fixed


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────
def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Church Name Standardization ({mode}) ===", flush=True)
    print(f"Phases: {PHASES}", flush=True)

    db = connect()

    with Provenance(db, source="name_standardizer",
                    action="updated", fields="name") as prov:
        total = 0

        if 1 in PHASES:
            total += run_phase1(db)

        if 2 in PHASES:
            total += run_phase2(db)

        if 3 in PHASES:
            total += run_phase3(db)

        if 4 in PHASES:
            total += run_phase4(db)

        prov.churches_updated = total

    # Final verification
    if not DRY_RUN:
        c = db.cursor()
        print("\n=== Verification ===", flush=True)
        checks = [
            ("' ST.' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST.%'"),
            ("' SAINT' total", "SELECT COUNT(*) FROM churches WHERE name LIKE '% SAINT %'"),
            ("' ST ' non-street", "SELECT COUNT(*) FROM churches WHERE name LIKE '% ST %' AND name NOT LIKE '% STREET %' AND name NOT LIKE '% ST.%'"),
            ("' MT.' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT.%'"),
            ("' CTR ' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% CTR %'"),
            ("' MT ' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% MT %' AND name NOT LIKE '% MT.%'"),
            ("' FT ' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% FT %' AND name NOT LIKE '% FT.%'"),
            ("' INC' remaining", "SELECT COUNT(*) FROM churches WHERE name LIKE '% INC' OR name LIKE '% INC.'"),
            ("' S at end (possessive?)", "SELECT COUNT(*) FROM churches WHERE (name LIKE '% SAINT % S' OR name LIKE 'SAINT % S') AND name NOT LIKE '% INC' AND name NOT LIKE '% INC.'"),
        ]
        for label, sql in checks:
            c.execute(sql)
            print(f"  {label}: {c.fetchone()[0]:,}", flush=True)

        # Show random samples
        print("\n--- Random samples ---", flush=True)
        for r in c.execute("SELECT id, name FROM churches ORDER BY RANDOM() LIMIT 10").fetchall():
            print(f"  [{r[0]}] {r[1][:90]}", flush=True)

    db.close()
    print(f"\n{'DRY RUN. ' if DRY_RUN else ''}Done. Total changes: {total:,}", flush=True)


if __name__ == '__main__':
    main()

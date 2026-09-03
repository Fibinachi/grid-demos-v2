"""
Review and fix umbrella corporate legal entities that are NOT actual church names.

These come from Canadian (especially Ontario) diocese-level corporations —
historically duplicates of the same legal shell entity entered as "churches".

Categories:
  1. DELETE: Pure legal entities — the entire name IS a diocese corporation
     e.g. "THE ROMAN CATHOLIC EPISCOPAL CORPORATION FOR THE DIOCESE OF TORONTO, IN CANADA"
     e.g. "CORPORATION OF THE PRESIDING BISHOP OF THE CHURCH OF JESUS CHRIST..."
  2. STRIP: Legal entity prefix with an actual church name appended
     e.g. "UKRAINIAN CATH EPISC CORP OF SASK ST DEMETRIUS UKR CATH CHURCH"
           → "ST DEMETRIUS UKR CATH CHURCH"

Usage:
    python _fix_umbrella.py                   # review batch 1
    python _fix_umbrella.py --batch 2
    python _fix_umbrella.py --apply           # apply ALL fixes
    python _fix_umbrella.py --apply --dry-run # preview
"""

import re
import sqlite3
import sys

DB_PATH = r'E:\grid\churches.db'
BATCH_SIZE = 40

# ─── DELETE: Names that are pure legal entities ──────────────────────
# These match the ENTIRE entity name. Only records where the name IS one
# of these patterns will be deleted.

DELETE_PREFIXES = [
    # Ontario RC diocese corporations
    r'^(?:THE\s+)?ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+(?:FOR|OF)\s+THE\s+DIOCESE\s+OF',
    r'^(?:THE\s+)?ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+(?:FOR|OF)\s+THE\s+ARCHDIOCESE\s+OF',
    r'^(?:THE\s+)?ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+OF\b',
    r'^(?:THE\s+)?ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+FOR\b',
    r'^ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+FOR\b',
    r'^ROMAN\s+CATHOLIC\s+EPISCOPAL\s+CORPORATION\s+OF\b',

    # LDS corporate entities
    r'^CORPORATION\s+OF\s+THE\s+PRESIDING\s+BISHOP\s+OF\b',
    r'^CORPORATION\s+OF\s+THE\s+PRESIDENT\s+OF\b',

    # Episcopal Corporation of [place] — pure legal shell
    r'^EPISCOPAL\s+CORPORATION\s+OF\b',
    r'^EPISCOPAL\s+CORPORATION\s+FOR\b',

    # Catholic Episcopal Corp of [place]
    r'^CATHOLIC\s+EPISCOPAL\s+CORP(?:ORATION)?\s+OF\b',
]

# ─── STRIP: Remove legal entity prefix to expose church name ────────
STRIP_RULES = [
    # "UKRAINIAN CATH EPISC CORP OF SASK ST DEMETRIUS UKR CATH CHURCH"
    (re.compile(
        r'^UKRAINIAN\s+CATH(?:\s+EPISC)?\s+CORP(?:\s+OF)?\s+SASK(?:ATCHEWAN)?\s+(.+)',
        re.IGNORECASE
    ), 'Strip Ukrainian Catholic Corp prefix'),
]

# ─── BUILD MASTER DELETE REGEX ──────────────────────────────────────
DELETE_RE = re.compile(
    '(' + ')|('.join(DELETE_PREFIXES) + ')',
    re.IGNORECASE
)

# ─── ABBREVIATION EXPANSION for Ukrainian records ───────────────────
# After stripping the corp prefix, expand abbreviations users may not know.
ABBREV_EXPANSIONS = [
    (re.compile(r'\b1ST\b'), 'FIRST'),
    (re.compile(r'\bUKR\b'), 'UKRAINIAN'),
    (re.compile(r'\bUKRA\b'), 'UKRAINIAN'),        # truncated "UKRA"
    (re.compile(r'\bCATH\b'), 'CATHOLIC'),
    (re.compile(r'\bCAATH\b'), 'CATHOLIC'),         # typo fix
]


def expand_abbrevs(name):
    """Expand abbreviations like UKR→UKRAINIAN, CATH→CATHOLIC in a name."""
    for pat, replacement in ABBREV_EXPANSIONS:
        name = pat.sub(replacement, name)
    return name


def classify(name):
    """Returns (action, new_name, desc) or None."""
    for pat, desc in STRIP_RULES:
        m = pat.match(name.strip())
        if m:
            remainder = m.group(1).strip()
            if len(remainder) >= 5:
                remainder = expand_abbrevs(remainder)
                return ('strip', remainder, desc)
            return ('delete', None, desc + ' (nothing after prefix)')

    if DELETE_RE.match(name.strip()):
        return ('delete', None, 'Pure legal entity')

    return None


def apply_fixes(classified, dry_run=False):
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    del_total = 0
    strip_total = 0

    for name, action, new_name, ids in classified:
        if action == 'delete':
            if dry_run:
                c = cur.execute("SELECT COUNT(*) FROM churches WHERE name = ?", (name,)).fetchone()[0]
            else:
                c = cur.execute("DELETE FROM churches WHERE name = ?", (name,))
                c = c.rowcount
            del_total += c
            if not dry_run:
                print(f"  DELETE {c}×: {name[:70]}")
        elif action == 'strip':
            if dry_run:
                c = cur.execute("SELECT COUNT(*) FROM churches WHERE name = ?", (name,)).fetchone()[0]
            else:
                c = cur.execute(
                    "UPDATE churches SET name = ? WHERE name = ?",
                    (new_name, name)
                ).rowcount
            strip_total += c
            if not dry_run:
                print(f"  STRIP {c}×: {name[:50]}… → {new_name[:50]}")

    if not dry_run:
        db.commit()
    db.close()
    return del_total, strip_total


def main():
    batch_num = 1
    show_only = False
    apply_all = False
    dry_run = False

    for i, a in enumerate(sys.argv):
        if a == '--batch' and i + 1 < len(sys.argv):
            batch_num = int(sys.argv[i + 1])
        if a == '--show-only':
            show_only = True
        if a == '--apply':
            apply_all = True
        if a == '--dry-run':
            dry_run = True

    # ── Query candidates ──
    db = sqlite3.connect(DB_PATH)
    cur = db.execute("SELECT id, name FROM churches ORDER BY id")
    all_rows = cur.fetchall()
    db.close()

    # Classify and dedupe
    name_map = {}
    for rid, name in all_rows:
        r = classify(name)
        if r:
            action, new_name, desc = r
            if name not in name_map:
                name_map[name] = (action, new_name, [])
            name_map[name][2].append(rid)

    classified = sorted(
        [(name, action, new_name, ids) for name, (action, new_name, ids) in name_map.items()],
        key=lambda x: (0 if x[1] == 'delete' else 1, x[0])
    )

    total_unique = len(classified)
    total_records = sum(len(ids) for _, _, _, ids in classified)

    if total_unique == 0:
        print("No umbrella entity records found.")
        return

    # ── APPLY mode ──
    if apply_all:
        print(f"=== UMBRELLA ENTITY FIX ===")
        if dry_run:
            print("  DRY RUN — no changes made")
        else:
            print("  APPLYING FIXES...")
        print()
        del_count, strip_count = apply_fixes(classified, dry_run=dry_run)
        print()
        print(f"  DELETE: {del_count:,} records removed (pure legal entities)")
        print(f"  STRIP:  {strip_count:,} records updated (prefix removed)")
        if dry_run:
            print("\n  Run with --apply (without --dry-run) to execute.")
        return

    # ── REVIEW mode ──
    offset = (batch_num - 1) * BATCH_SIZE
    page = classified[offset:offset + BATCH_SIZE]

    print("=" * 110)
    print(f"  UMBRELLA ENTITY FIX — (unique patterns: {total_unique}, total records: {total_records:,})")
    print(f"  Batch {batch_num} (rows {offset+1}-{offset+len(page)} of {total_unique})")
    print("=" * 110)
    print()

    for i, (name, action, new_name, ids) in enumerate(page):
        num = offset + i + 1
        nids = [str(x) for x in ids[:5] if x is not None]
        extra = f" [+{len(ids)-5} more]" if len(ids) > 5 else ""
        label = f"id={','.join(nids)}{extra}" if nids else ""
        print(f"  [{num:3d}] ×{len(ids)}  {label}  [{len(name):3d}]")
        if action == 'delete':
            print(f"         DELETE: {name}")
        elif action == 'strip':
            print(f"         STRIP:  {name}")
            print(f"         → NEW:  {new_name}")
        print()

    strip_uniq = sum(1 for _, a, _, _ in classified if a == 'strip')
    del_uniq = sum(1 for _, a, _, _ in classified if a == 'delete')
    strip_recs = sum(len(ids) for _, a, _, ids in classified if a == 'strip')
    del_recs = sum(len(ids) for _, a, _, ids in classified if a == 'delete')
    print(f"{'─' * 110}")
    print(f"  DELETE: {del_uniq} patterns → {del_recs:,} records")
    print(f"  STRIP:  {strip_uniq} patterns → {strip_recs:,} records")
    print()

    if not show_only:
        if total_unique > offset + len(page):
            print(f"  Next: python _fix_umbrella.py --batch {batch_num + 1}")
        else:
            print("  ✓ All batches shown.")
            print(f"  To apply: python _fix_umbrella.py --apply")
            print(f"  To preview: python _fix_umbrella.py --apply --dry-run")


if __name__ == '__main__':
    main()

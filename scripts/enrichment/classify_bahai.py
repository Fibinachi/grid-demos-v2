#!/usr/bin/env python3
"""
Baháʼí Faith Classification
============================
Tags 1,914 Baháʼí records with proper faith_tradition, family, and org type.

Baháʼí organizational taxonomy:
  - Local Spiritual Assembly (LSA) — city/county governing body
  - National Spiritual Assembly (NSA) — national governing body
  - Baháʼí Center — local meeting place
  - Baháʼí Temple / House of Worship — continental temples
  - Baháʼí Institute — training center
"""
import argparse, re, sqlite3, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')


def classify_type(name):
    """Classify the Baháʼí org type."""
    nl = (name or '').lower().strip()
    
    if re.search(r'\btemple\b', nl) or re.search(r'\bhouse\s+of\s+worship\b', nl):
        return 'Baháʼí Temple'
    if re.search(r'\bnational\s+spiritual\s+assembly\b', nl):
        return 'National Spiritual Assembly'
    if re.search(r'\blocal\s+spiritual\s+assembly\b', nl) or re.search(r'\bspiritual\s+assembly\b', nl):
        return 'Local Spiritual Assembly'
    if re.search(r'\bcenter\b', nl) or re.search(r'\bcenter\b', nl):
        return 'Baháʼí Center'
    if re.search(r'\binstitute\b', nl):
        return 'Baháʼí Institute'
    if re.search(r'\bbahais?\s+of\b', nl):
        return 'Local Spiritual Assembly'  # "Baháʼís of [City]" = LSA
    return 'Baháʼí (General)'


def main():
    parser = argparse.ArgumentParser(description='Baháʼí classification')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)

    rows = db.execute("""
        SELECT id, name, city, state FROM churches
        WHERE LOWER(name) LIKE '%bahai%'
        ORDER BY id
    """).fetchall()

    print(f'Baháʼí records: {len(rows):,}')

    if args.dry_run:
        types = {}
        for r in rows:
            t = classify_type(r[1])
            types[t] = types.get(t, 0) + 1
        print(f'\nOrg type breakdown:')
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            print(f'  {t:30s} {c:>6,}')
        print(f'\nSample:')
        for r in rows[:10]:
            print(f'  {r[0]:>8d} | {r[1][:55]:55s} -> {classify_type(r[1])}')
        db.close()
        return

    type_counts = {}
    for r in rows:
        org_type = classify_type(r[1])
        type_counts[org_type] = type_counts.get(org_type, 0) + 1
        db.execute("""
            UPDATE churches SET
                faith_tradition = 'other',
                family = 'Bahai',
                denomination = ?,
                last_updated = datetime('now')
            WHERE id = ?
        """, (org_type, r[0]))

    db.commit()
    print(f'  Updated: {len(rows):,} records')
    print(f'\n{"Org Type":30s} {"Count":>6s}')
    print('-' * 40)
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f'{t:30s} {c:>6,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

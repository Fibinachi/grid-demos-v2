#!/usr/bin/env python3
"""
Scientology Classification + Full Taxonomy
===========================================
Classifies records with Scientology-matching names into the full
organizational taxonomy based on naming patterns.

Taxonomy:
  Class V Org — standard local church
  Ideal Org — flagship newly-built org
  Advanced Org (AO) — delivers OT levels
  Saint Hill Org — delivers Saint Hill Special Briefing Course
  Flag Service Org (FSO) — Clearwater FL headquarters
  Flag Ship Service Org (FSSO) — Freewinds ship
  Celebrity Centre — celeb-focused orgs
  Mission — smaller outreach units
  Continental Liaison Office (CLO) — regional admin
  Support Organization — Golden Era, Bridge, New Era, etc.
"""
import argparse, re, sqlite3, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')


def classify_type(name):
    nl = (name or '').lower().strip()
    
    if re.search(r'\bflag\b.*\bservice\b|\bflag\s+land\s+base\b|clearwater.*flag', nl):
        return 'Flag Service Org'
    if re.search(r'\bfreewinds\b|\bflag\s+ship\b', nl):
        return 'Flag Ship Service Org'
    if re.search(r'\badvanced\s+(org|organization)\b|\badvanced org\b|\badvanced.*saint.?hill\b', nl):
        return 'Advanced Org'
    if re.search(r'\bsaint.?hill\b|\bst\.?\s*hill\b', nl) and 'advanced' not in nl:
        return 'Saint Hill Org'
    if re.search(r'\bideal\s', nl) or re.search(r'\bgrand\s+opening\b', nl):
        return 'Ideal Org'
    if re.search(r'\bcelebrity\s*(centre|center)\b', nl):
        return 'Celebrity Centre'
    if re.search(r'\bmission\b', nl):
        return 'Mission'
    if re.search(r'\bcontinental\s+liaison\b|\bclo\b', nl):
        return 'Continental Liaison Office'
    if re.search(r'\bgolden.?era\b|\bbridge\s+publications\b|\bnew.?era\s+publications\b|\bscientology\s+media\b|\bdissemination\b', nl):
        return 'Support Organization'
    return 'Class V Org'


def main():
    parser = argparse.ArgumentParser(description='Scientology classification')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)

    rows = db.execute("""
        SELECT id, name, city, state FROM churches
        WHERE LOWER(name) LIKE '%scientolog%'
        ORDER BY id
    """).fetchall()

    print(f'Scientology records: {len(rows):,}')

    if args.dry_run:
        for r in rows:
            print(f'  {r[0]:>8d} | {r[1][:55]:55s} | {r[2]:18s} {r[3]:3s}')
        db.close()
        return

    # Update faith_tradition, family, denomination with taxonomy
    type_counts = {}
    for r in rows:
        org_type = classify_type(r[1])
        type_counts[org_type] = type_counts.get(org_type, 0) + 1
        db.execute("""
            UPDATE churches SET
                faith_tradition = 'other',
                family = 'Scientology',
                denomination = ?,
                last_updated = datetime('now')
            WHERE id = ?
        """, (org_type, r[0]))

    db.commit()
    print(f'  Updated: {len(rows):,} records')

    # Report with type breakdown
    r = db.execute("SELECT denomination, COUNT(*) FROM churches WHERE family='Scientology' GROUP BY denomination ORDER BY COUNT(*) DESC").fetchall()
    print(f'\n{"Org Type":30s} {"Count":>6s}')
    print('-' * 40)
    for x in r:
        print(f'{x[0]:30s} {x[1]:>6,}')
    print(f'  TOTAL: {sum(x[1] for x in r):>6,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

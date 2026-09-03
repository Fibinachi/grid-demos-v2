#!/usr/bin/env python3
"""
LDS (Latter-day Saint) Classification
======================================
Identifies and classifies LDS churches by organizational level:
  Temple → Stake → Ward/Branch → Institute/Mission → Other LDS

LDS naming is very distinctive:
  - "Stake" — exclusively LDS, followed by geographic area
  - "Ward" + numbered (1st, 2nd) — LDS-specific
  - "Church of Jesus Christ of Latter-day Saints" — explicit
  - "Deseret" — strong LDS signal
  - "Institute of Religion" — often LDS

Usage:
    python scripts/enrichment/classify_lds.py
    python scripts/enrichment/classify_lds.py --dry-run
"""
import argparse, re, sqlite3, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# Confidence
EXPLICIT = 0.95
STRONG = 0.85
GOOD = 0.70

# LDS name patterns — ordered by specificity
LDS_RULES = [
    # Temples (highest level)
    (r'\btemple\b', 'LDS Temple', STRONG, 'lds_temple',
     lambda n, nl: bool(re.search(r'lds\s+temple|latter.day\s+temple|deseret\s+temple', nl) or
                         (re.search(r'temple', nl) and re.search(r'church\s+of\s+jesus\s+christ', nl)))),

    # Stakes (exclusively LDS)
    (r'\bstake\b', 'LDS Stake', EXPLICIT, 'lds_stake',
     lambda n, nl: True),

    # Wards (LDS-specific when numbered + church context)
    (r'\b\d+(st|nd|rd|th)\s+ward\b', 'LDS Ward', EXPLICIT, 'lds_ward_numbered',
     lambda n, nl: True),
    (r'\byoung\s+single\s+adult\s+ward\b', 'LDS Ward (YSA)', EXPLICIT, 'lds_ward_ysa',
     lambda n, nl: True),
    (r'\bsingles?\s+ward\b', 'LDS Ward (Singles)', EXPLICIT, 'lds_ward_singles',
     lambda n, nl: not re.search(r'baptist|methodist|presbyterian', nl)),

    # Explicit church name
    (r'\bchurch\s+of\s+jesus\s+christ\s+of\s+latter[-\s]?day\s+saints?\b', 'LDS (General)', EXPLICIT, 'lds_explicit',
     lambda n, nl: True),

    # Deseret
    (r'\bdeseret\b', 'LDS (General)', STRONG, 'lds_deseret',
     lambda n, nl: True),

    # LDS abbreviation
    (r'\blds\b', 'LDS (General)', STRONG, 'lds_abbr',
     lambda n, nl: not re.search(r'ministr|mission|baptist|church\s+of\s+god', nl)),

    # Institute of Religion (often LDS)
    (r'\binstitute\s+of\s+religion\b', 'LDS Institute', STRONG, 'lds_institute',
     lambda n, nl: True),

    # Meetinghouse (often LDS-specific when standalone)
    (r'\bmeetinghouse\b', 'LDS (General)', GOOD, 'lds_meetinghouse',
     lambda n, nl: not re.search(r'baptist|methodist|presbyterian|church\s+of\s+god|evangelical', nl)),

    # Mormon (the church prefers the full name, but still used informally)
    (r'\bmormon\b', 'LDS (General)', STRONG, 'lds_mormon',
     lambda n, nl: not re.search(r'anti.mormon|ex.mormon|former\s+mormon', nl)),

    # BYU-related (unique LDS signal)
    (r'\bbyu\b', 'LDS Institute', STRONG, 'lds_byu',
     lambda n, nl: True),
]

# State-level LDS inference
LDS_STATES = {
    'UT': ('LDS (General)', 0.65, 'state_utah_lds'),
    'ID': ('LDS (General)', 0.50, 'state_idaho_lds'),
}

# "Ward" alone (without number) — noisy, but strong in LDS-heavy states
WARD_NOISY = r'\bward\b'

# "Branch" — used by LDS but also many other groups
BRANCH_NOISY = r'\bbranch\b'


def classify_lds(name, state):
    """Returns (lds_type, confidence, source) or None if not LDS."""
    nl = (name or '').lower().strip()
    if not nl:
        return None

    for pattern, lds_type, conf, source, validator in LDS_RULES:
        if re.search(pattern, nl):
            if validator(name, nl):
                return lds_type, conf, source

    return None


def is_likely_lds(name, state):
    """Second pass — broader net for LDS-heavy states."""
    nl = (name or '').lower().strip()
    if not nl:
        return False
    
    # "1st Ward" or "2nd Ward" in any state
    if re.search(r'\d+(st|nd|rd|th)\s+ward', nl):
        return True
    
    # "Ward" in Utah/Idaho with church context
    if state in ('UT', 'ID') and re.search(r'\bward\b', nl) and re.search(r'\bchurch\b', nl):
        return True
    
    # "Branch" in Utah/Idaho
    if state in ('UT', 'ID') and re.search(r'\bbranch\b', nl) and re.search(r'\bchurch\b', nl):
        return True
    
    return False


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('lds_type', 'TEXT'),
        ('lds_confidence', 'REAL'),
        ('lds_source', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')


def main():
    parser = argparse.ArgumentParser(description='LDS classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--broad', action='store_true',
                        help='Broad search (include UT/ID wards and branches)')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    # Get candidates by precise LDS patterns
    rows = db.execute("""
        SELECT id, name, city, state FROM churches
        WHERE (LOWER(name) LIKE '%church of jesus christ of latter%'
           OR LOWER(name) LIKE '%stake%'
           OR LOWER(name) LIKE '%lds%'
           OR LOWER(name) LIKE '%deseret%'
           OR LOWER(name) LIKE '%mormon%'
           OR LOWER(name) LIKE '%meetinghouse%'
           OR LOWER(name) LIKE '%institute of religion%'
           OR LOWER(name) LIKE '%byu%')
        ORDER BY id
    """).fetchall()
    
    # Also include numbered wards
    ward_rows = db.execute("""
        SELECT id, name, city, state FROM churches
        WHERE (LOWER(name) GLOB '*[0-9][st|nd|rd|th] ward*')
        ORDER BY id
    """).fetchall()
    
    # Merge, deduplicate
    seen = {r[0] for r in rows}
    all_rows = list(rows) + [r for r in ward_rows if r[0] not in seen]

    # Broad mode: add UT/ID wards and branches
    if args.broad:
        extra = db.execute("""
            SELECT id, name, city, state FROM churches
            WHERE state IN ('UT', 'ID')
            AND (LOWER(name) LIKE '%ward%' OR LOWER(name) LIKE '%branch%')
            AND id NOT IN ({})
        """.format(','.join(str(r[0]) for r in all_rows) if all_rows else '0')).fetchall()
        all_rows.extend(extra)

    print(f'LDS candidates to classify: {len(all_rows):,}')

    if args.dry_run:
        for r in all_rows[:20]:
            result = classify_lds(r[1], r[3])
            if result:
                print(f'  LDS {r[0]:>8d} | {r[1][:55]:55s} -> {result[0]:20s} (c={result[1]:.2f})')
            else:
                print(f'  ?   {r[0]:>8d} | {r[1][:55]:55s} -> no match')
        db.close()
        return

    classified = 0
    for r in all_rows:
        result = classify_lds(r[1], r[3])
        if result:
            lds_type, conf, source = result
            db.execute("""
                UPDATE churches SET
                    lds_type = ?,
                    lds_confidence = ?,
                    lds_source = ?,
                    last_updated = datetime('now')
                WHERE id = ?
            """, (lds_type, conf, source, r[0]))
            classified += 1

    db.commit()

    # Report
    rs = db.execute("""
        SELECT lds_type, COUNT(*) as c, ROUND(AVG(lds_confidence), 2) as conf
        FROM churches WHERE lds_type != '' GROUP BY lds_type ORDER BY c DESC
    """).fetchall()
    print(f'\n{"Type":25s} {"Count":>6s} {"Conf":>6s}')
    print('-' * 40)
    total = 0
    for r in rs:
        print(f'{r[0]:25s} {r[1]:>6,} {r[2]:>6.2f}')
        total += r[1]
    
    rs = db.execute("SELECT COUNT(*) FROM churches WHERE lds_type IS NOT NULL AND lds_type != ''").fetchone()
    print(f'\nTotal classified: {total:,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

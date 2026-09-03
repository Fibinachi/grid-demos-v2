#!/usr/bin/env python3
"""
Sikh & Jain Classification
===========================
Classifies Sikh gurdwaras and Jain derasars by organization type
using name patterns.

Sikh categories:
  - Gurdwara (generic)
  - Khalsa School
  - Sikh Center
  - Sikh Society

Jain categories:
  - Derasar
  - Jain Center
  - Swetambar
  - Digambar

Premium API: This classifier powers a paid API endpoint.
Output includes: sikh_affiliation, jain_affiliation, confidence

Usage:
    python scripts/enrichment/classify_sikh_jain.py
    python scripts/enrichment/classify_sikh_jain.py --dry-run
    python scripts/enrichment/classify_sikh_jain.py --reprocess
    python scripts/enrichment/classify_sikh_jain.py --limit 100
"""
import argparse
import re
import sqlite3
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

EXPLICIT = 0.95
STRONG_NAME = 0.80
GOOD_NAME = 0.70
MODERATE = 0.55

# ═══════════════════════════════════════════════════════════════════
# SIKH KEYWORDS
# ═══════════════════════════════════════════════════════════════════

SIKH_RULES = [
    (r'\bgurdwara\b', 'Gurdwara', EXPLICIT, 'gurdwara'),
    (r'\bgurudwara\b', 'Gurdwara', EXPLICIT, 'gurudwara'),
    (r'\bguru\s+nanak\b', 'Gurdwara (Nanakshahi)', STRONG_NAME, 'guru_nanak'),
    (r'\bguru\s+gobind\b', 'Gurdwara', STRONG_NAME, 'guru_gobind'),
    (r'\bguru\s+granth\b', 'Gurdwara', STRONG_NAME, 'guru_granth'),
    (r'\bguru\s+ram.das\b', 'Gurdwara', STRONG_NAME, 'guru_ram_das'),
    (r'\bguru\s+angad\b', 'Gurdwara', STRONG_NAME, 'guru_angad'),
    (r'\bguru\s+arjun\b', 'Gurdwara', STRONG_NAME, 'guru_arjun'),
    (r'\bguru\s+har[ig].\b', 'Gurdwara', STRONG_NAME, 'guru_hari'),
    (r'\bguru\s+tegh\b', 'Gurdwara', STRONG_NAME, 'guru_tegh'),
    (r'\bguru\s+goind\b', 'Gurdwara', STRONG_NAME, 'guru_goind'),
    (r'\bkhalsa\s+(school|academy|center|international)\b', 'Khalsa School', EXPLICIT, 'khalsa_school'),
    (r'\bkhalsa\b', 'Gurdwara', MODERATE, 'khalsa'),
    (r'\bsikh\s+center\b', 'Sikh Center', EXPLICIT, 'sikh_center'),
    (r'\bsikh\s+(temple|gurdwara|society|association|congregation|community|church)\b', 'Sikh Center', STRONG_NAME, 'sikh_org'),
    (r'\bsikh\s+(society|foundation)\b', 'Sikh Society', EXPLICIT, 'sikh_society'),
    (r'\b(sikh|sikhi)\s*(foundation|mission|cultural)\b', 'Sikh Society', STRONG_NAME, 'sikh_foundation'),
    (r'\bsikh\b', 'Sikh (Generic)', MODERATE, 'sikh_keyword'),
    (r'\bpunjab\s+(sikh|society|center|cultural|association)\b', 'Sikh Society', STRONG_NAME, 'punjab_sikh'),
    (r'\bnanak\s+(darbar|sahib|mission|foundation)\b', 'Gurdwara', STRONG_NAME, 'nanak_org'),
    (r'\blion\s+of\s+punjab\b', 'Gurdwara', MODERATE, 'lion_of_punjab'),
    (r'\bnishan\s+sahib\b', 'Gurdwara', EXPLICIT, 'nishan_sahib'),
]

# ═══════════════════════════════════════════════════════════════════
# JAIN KEYWORDS
# ═══════════════════════════════════════════════════════════════════

JAIN_RULES = [
    (r'\bderasar\b', 'Derasar', EXPLICIT, 'derasar'),
    (r'\bderasaar\b', 'Derasar', EXPLICIT, 'derasaar'),
    (r'\bjain\s+(center|association|society|foundation|cultural|temple|mandir|community)\b', 'Jain Center', STRONG_NAME, 'jain_center'),
    (r'\bjain\s+(sangh|sangha|samaj|samiti)\b', 'Jain Center', STRONG_NAME, 'jain_sangh'),
    (r'\bswetambar\b', 'Swetambar', EXPLICIT, 'swetambar'),
    (r'\bshwetambar\b', 'Swetambar', EXPLICIT, 'shwetambar'),
    (r'\bdigambar\b', 'Digambar', EXPLICIT, 'digambar'),
    (r'\bjain\s+(study|education|academy|prayer)\b', 'Jain Center', STRONG_NAME, 'jain_education'),
    (r'\bjain\b', 'Jain (Generic)', MODERATE, 'jain_keyword'),
    (r'\bmahavir\b', 'Jain (Generic)', MODERATE, 'mahavir'),
    (r'\bparshvanath\b', 'Jain (Generic)', STRONG_NAME, 'parshvanath'),
    (r'\bmandir\s+mahavir\b', 'Jain Center', STRONG_NAME, 'mandir_mahavir'),
    (r'\b(upadhyay|acharya|muni)\b', 'Jain (Generic)', MODERATE, 'jain_title'),
]


# ═══════════════════════════════════════════════════════════════════
# CLASSIFIER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def classify_sikh(name):
    """Classify Sikh organization type from name."""
    nl = (name or '').lower()
    if not nl:
        return None, 0, None
    for pattern, aff, conf, src in SIKH_RULES:
        if re.search(pattern, nl):
            return aff, conf, src
    return None, 0, None


def classify_jain(name):
    """Classify Jain organization type from name."""
    nl = (name or '').lower()
    if not nl:
        return None, 0, None
    for pattern, aff, conf, src in JAIN_RULES:
        if re.search(pattern, nl):
            return aff, conf, src
    return None, 0, None


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('sikh_affiliation', 'TEXT'),
        ('sikh_confidence', 'REAL'),
        ('sikh_classification_source', 'TEXT'),
        ('sikh_updated', 'TEXT'),
        ('jain_affiliation', 'TEXT'),
        ('jain_confidence', 'REAL'),
        ('jain_classification_source', 'TEXT'),
        ('jain_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def main():
    parser = argparse.ArgumentParser(description='Sikh & Jain classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    # ── SIKH ──
    sikh_where = '' if args.reprocess else "AND (sikh_affiliation IS NULL OR sikh_affiliation = '')"
    sikh_limit = f'LIMIT {args.limit}' if args.limit else ''
    sikh_rows = db.execute(f"""
        SELECT id, name, city, state
        FROM churches
        WHERE faith_tradition = 'sikh'
        {sikh_where}
        ORDER BY id
        {sikh_limit}
    """).fetchall()

    print(f'Sikh records to classify: {len(sikh_rows):,}')

    if args.dry_run:
        sikh_counts = {}
        for r in sikh_rows[:50]:
            aff, conf, src = classify_sikh(r[1])
            if aff:
                sikh_counts[aff] = sikh_counts.get(aff, 0) + 1
            else:
                sikh_counts['(unmatched)'] = sikh_counts.get('(unmatched)', 0) + 1
        print(f'\n{"Sikh Type":30s} {"Count":>6s}')
        print('-' * 40)
        for a, c in sorted(sikh_counts.items(), key=lambda x: -x[1]):
            print(f'{a:30s} {c:>6,}')

        print(f'\nSikh sample:')
        for r in sikh_rows[:5]:
            aff, conf, src = classify_sikh(r[1])
            print(f'  {r[0]:>8d} | {r[1][:50]:50s} -> {aff or "no match":30s}')
    else:
        sikh_matches = 0
        for r in sikh_rows:
            aff, conf, src = classify_sikh(r[1])
            if aff:
                db.execute("""
                    UPDATE churches SET
                        sikh_affiliation = ?,
                        sikh_confidence = ?,
                        sikh_classification_source = ?,
                        sikh_updated = datetime('now'),
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (aff, conf, src, r[0]))
                sikh_matches += 1
        db.commit()
        print(f'  Name heuristic: {sikh_matches:,} / {len(sikh_rows):,} matched')

    # ── JAIN ──
    # Jain doesn't have its own faith_tradition — they're in 'other'
    # Match via 'jain' keyword in name or denomination
    jain_where = '' if args.reprocess else "AND (jain_affiliation IS NULL OR jain_affiliation = '')"
    jain_limit = f'LIMIT {args.limit}' if args.limit else ''
    jain_rows = db.execute(f"""
        SELECT id, name, city, state
        FROM churches
        WHERE (faith_tradition = 'other' OR faith_tradition IS NULL)
          AND (LOWER(name) LIKE '%jain%' OR LOWER(denomination) LIKE '%jain%')
        {jain_where}
        ORDER BY id
        {jain_limit}
    """).fetchall()

    print(f'\nJain records to classify: {len(jain_rows):,}')

    if args.dry_run:
        jain_counts = {}
        for r in jain_rows[:50]:
            aff, conf, src = classify_jain(r[1])
            if aff:
                jain_counts[aff] = jain_counts.get(aff, 0) + 1
            else:
                jain_counts['(unmatched)'] = jain_counts.get('(unmatched)', 0) + 1
        print(f'\n{"Jain Type":30s} {"Count":>6s}')
        print('-' * 40)
        for a, c in sorted(jain_counts.items(), key=lambda x: -x[1]):
            print(f'{a:30s} {c:>6,}')
        print(f'\nJain sample:')
        for r in jain_rows[:5]:
            aff, conf, src = classify_jain(r[1])
            print(f'  {r[0]:>8d} | {r[1][:50]:50s} -> {aff or "no match":30s}')
    else:
        jain_matches = 0
        for r in jain_rows:
            aff, conf, src = classify_jain(r[1])
            if aff:
                db.execute("""
                    UPDATE churches SET
                        jain_affiliation = ?,
                        jain_confidence = ?,
                        jain_classification_source = ?,
                        jain_updated = datetime('now'),
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (aff, conf, src, r[0]))
                jain_matches += 1
        db.commit()
        print(f'  Name heuristic: {jain_matches:,} / {len(jain_rows):,} matched')

    if not args.dry_run:
        # Report
        for label, col in [('SIKH', 'sikh_affiliation'), ('JAIN', 'jain_affiliation')]:
            rs = db.execute(f"""
                SELECT {col}, COUNT(*) as cnt,
                       ROUND(AVG({col.replace('affiliation','confidence')}), 3) as avg_conf
                FROM churches
                WHERE {col} != '' AND {col} IS NOT NULL
                GROUP BY {col}
                ORDER BY cnt DESC
            """).fetchall()
            if rs:
                print(f'\n=== {label} RESULTS ===')
                print(f'{"Type":30s} {"Count":>7s} {"Avg Conf":>8s}')
                print('-' * 50)
                for r in rs:
                    print(f'{r[0]:30s} {r[1]:>7,} {r[2]:>8.3f}')

        rs = db.execute("""
            SELECT COUNT(*) FROM churches
            WHERE faith_tradition = 'sikh'
            AND (sikh_affiliation IS NULL OR sikh_affiliation = '')
        """).fetchone()
        print(f'\nSikh unclassified: {rs[0]:,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

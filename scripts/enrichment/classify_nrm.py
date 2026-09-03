#!/usr/bin/env python3
"""
NRM (New Religious Movement) Classification
=============================================
Classifies non-mainstream religious organizations into academic NRM taxonomy.

Categories:
  - New Thought / Metaphysical (Unity, Religious Science, Science of Mind, Divine Science)
  - Esoteric / Occult / Mystery School (Theosophy, Anthroposophy, Rosicrucian, Golden Dawn, Gnostic)
  - New Age / Alternative Spirituality (Eckankar, Course in Miracles, TM, Aurobindo, Brahma Kumaris)
  - UFO / Extraterrestrial Religion (Raelian, Aetherius, Unarius, Heaven's Gate)
  - NeoPagan / Earth-Based (Wicca, Druid, Asatru/Heathenry, General Pagan)
  - High-Demand NRM (Scientology, Unification Church, Jehovah's Witnesses)
  - Spiritualist Church
  - Intentional Community (Ashrams, Monasteries, Ecovillages)
  - Mormon Fundamentalist

This becomes the first national NRM infrastructure dataset.
Premium API: Powers a paid API endpoint for religious research.

Usage:
    python scripts/enrichment/classify_nrm.py
    python scripts/enrichment/classify_nrm.py --dry-run
    python scripts/enrichment/classify_nrm.py --reprocess
    python scripts/enrichment/classify_nrm.py --limit 100
"""
import argparse
import re
import sqlite3
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

EXPLICIT = 0.95
STRONG_NAME = 0.85
GOOD_NAME = 0.75
MODERATE = 0.60
WEAK = 0.45
GENERIC = 0.30

# ═══════════════════════════════════════════════════════════════════
# NRM NAME RULES — ordered by specificity per category
# Each rule: (regex_pattern, category, subcategory, confidence, source_tag)
# ═══════════════════════════════════════════════════════════════════

# ── Exclusion patterns: names that look like NRM but are actually mainstream ──
# e.g. "Unity Temple Church of God in Christ", "Circle of Hope Church"
CHRISTIAN_EXCLUSIONS = [
    r'\bbaptist\b', r'\bchurch of god\b', r'\bmethodist\b', r'\blutheran\b',
    r'\bpresbyterian\b', r'\bpentecostal\b', r'\bcatholic\b', r'\bepiscopal\b',
    r'\bcongregational\b', r'\breformed\b', r'\bcalvary\b', r'\bmissionary baptist\b',
    r'\bfirst\s+\w+\s+baptist\b', r'\bgospel\b', r'\btabernacle\b',
    r'\bkorean\b', r'\bspanish\b', r'\blatino\b', r'\bhispano\b',
    r'\bchristian\b', r'\bjesus christ\b', r'\blord\b', r'\bsavior\b',
    r'\bchurch of christ\b', r'\bnazarene\b', r'\bassembly of god\b',
    r'\bjerusalem\b', r'\bzion\b',
]

RULES = [
    # ── NEW THOUGHT ──
    (r'\breligious science\b', 'New Thought', 'Religious Science', EXPLICIT, 'religious_science'),
    (r'\bscience of mind\b', 'New Thought', 'Science of Mind', EXPLICIT, 'science_of_mind'),
    (r'\bdivine science\b', 'New Thought', 'Divine Science', EXPLICIT, 'divine_science'),
    (r'\bageless wisdom\b', 'New Thought', 'Ageless Wisdom', EXPLICIT, 'ageless_wisdom'),
    # Unity Church (New Thought) — must NOT be mainstream Christian
    (r'\bunity church of\b', 'New Thought', 'Unity', GOOD_NAME, 'unity_church_of'),
    (r'\bunity on the\b', 'New Thought', 'Unity', GOOD_NAME, 'unity_on'),
    (r'\bunity of\b', 'New Thought', 'Unity', GOOD_NAME, 'unity_of'),
    (r'\bunity spiritual\b', 'New Thought', 'Unity', GOOD_NAME, 'unity_spiritual'),
    (r'\bunity center\b', 'New Thought', 'Unity', GOOD_NAME, 'unity_center'),
    (r'\bmetaphysical\b', 'New Thought', 'Metaphysical', MODERATE, 'metaphysical'),

    # ── ESOTERIC / MYSTERY SCHOOL ──
    (r'\btheosoph\w*\b', 'Esoteric', 'Theosophy', EXPLICIT, 'theosophy'),
    (r'\bblavatsky\b', 'Esoteric', 'Theosophy', EXPLICIT, 'blavatsky'),
    (r'\badyar\b', 'Esoteric', 'Theosophy', EXPLICIT, 'adyar'),
    (r'\bkrotona\b', 'Esoteric', 'Theosophy', STRONG_NAME, 'krotona'),
    (r'\banthroposoph\w*\b', 'Esoteric', 'Anthroposophy', EXPLICIT, 'anthroposophy'),
    (r'\brudolf steiner\b', 'Esoteric', 'Anthroposophy', EXPLICIT, 'rudolf_steiner'),
    (r'\brosicrucian\b', 'Esoteric', 'Rosicrucian', EXPLICIT, 'rosicrucian'),
    (r'\bamorc\b', 'Esoteric', 'Rosicrucian', EXPLICIT, 'amorc'),
    (r'\bbuilders of the adytum\b', 'Esoteric', 'Rosicrucian', EXPLICIT, 'bota'),
    (r'\bhermetic\b', 'Esoteric', 'Hermetic', EXPLICIT, 'hermetic'),
    (r'\bgolden dawn\b', 'Esoteric', 'Golden Dawn', EXPLICIT, 'golden_dawn'),
    (r'\bqabalah\b', 'Esoteric', 'Qabalah', EXPLICIT, 'qabalah'),
    (r'\bgnostic\b', 'Esoteric', 'Gnostic', STRONG_NAME, 'gnostic'),

    # ── NEW AGE ──
    (r'\beckankar\b', 'New Age', 'Eckankar', EXPLICIT, 'eckankar'),
    (r'\bcourse in miracles\b', 'New Age', 'Course in Miracles', EXPLICIT, 'acim'),
    (r'\btranscendental meditation\b', 'New Age', 'TM', EXPLICIT, 'tm'),
    (r'\bmaharshi\b', 'New Age', 'TM', STRONG_NAME, 'maharshi'),
    (r'\bbrahma kumaris?\b', 'New Age', 'Brahma Kumaris', EXPLICIT, 'brahma_kumaris'),
    (r'\bsathya sai\b', 'New Age', 'Sathya Sai', EXPLICIT, 'sathya_sai'),
    (r'\bsai baba\b', 'New Age', 'Sathya Sai', MODERATE, 'sai_baba'),
    (r'\baurobindo\b', 'New Age', 'Sri Aurobindo', EXPLICIT, 'aurobindo'),
    (r'\bfindhorn\b', 'New Age', 'Findhorn', EXPLICIT, 'findhorn'),
    (r'\bnew age\b', 'New Age', 'New Age (General)', MODERATE, 'new_age'),

    # ── UFO RELIGION ──
    (r'\baetherius\b', 'UFO Religion', 'Aetherius Society', EXPLICIT, 'aetherius'),
    (r'\bunarius\b', 'UFO Religion', 'Unarius', EXPLICIT, 'unarius'),
    (r"\bheaven.s? gate\b", 'UFO Religion', "Heaven's Gate", EXPLICIT, 'heavens_gate'),
    (r'\bummo\b', 'UFO Religion', 'Ummo', EXPLICIT, 'ummo'),
    # Raelian — must not match "israel"
    (r'\braelian\b', 'UFO Religion', 'Raelian', EXPLICIT, 'raelian'),

    # ── NEO-PAGAN ──
    (r'\bwicca[n]?\b', 'NeoPagan', 'Wicca', EXPLICIT, 'wicca'),
    (r'\bcoven\b', 'NeoPagan', 'Wicca', STRONG_NAME, 'coven'),
    (r'\bgoddess temple\b', 'NeoPagan', 'Wicca', STRONG_NAME, 'goddess_temple'),
    (r'\bpriestess\b', 'NeoPagan', 'Wicca', GOOD_NAME, 'priestess'),
    (r'\bdruid\b', 'NeoPagan', 'Druid', EXPLICIT, 'druid'),
    (r'\basatru\b', 'NeoPagan', 'Heathen', EXPLICIT, 'asatru'),
    (r'\bheathen\b', 'NeoPagan', 'Heathen', STRONG_NAME, 'heathen'),
    (r'\bodin[ic]?\b', 'NeoPagan', 'Heathen', GOOD_NAME, 'odin'),
    (r'\bthor\b', 'NeoPagan', 'Heathen', MODERATE, 'thor'),
    (r'\bnorse\b', 'NeoPagan', 'Heathen', MODERATE, 'norse'),
    (r'\bearth centered\b', 'NeoPagan', 'Earth-Based (General)', MODERATE, 'earth_centered'),
    (r'\bpagan\b', 'NeoPagan', 'Pagan (General)', MODERATE, 'pagan'),

    # ── SPIRITUALIST ──
    (r'\bspiritualist\b', 'Spiritualist', 'Spiritualist Church', STRONG_NAME, 'spiritualist'),

    # ── HIGH-DEMAND NRM ──
    (r'\bscientolog\w*\b', 'NRM (High-Demand)', 'Scientology', EXPLICIT, 'scientology'),
    (r'\bdianetics\b', 'NRM (High-Demand)', 'Scientology', EXPLICIT, 'dianetics'),
    (r'\bl ron hubbard\b', 'NRM (High-Demand)', 'Scientology', EXPLICIT, 'lrh'),
    (r'\bhubbard\b', 'NRM (High-Demand)', 'Scientology', GOOD_NAME, 'hubbard'),
    (r'\bunification\b', 'NRM (High-Demand)', 'Unification Church', MODERATE, 'unification'),
    (r'\bfamily federation\b', 'NRM (High-Demand)', 'Unification Church', EXPLICIT, 'family_fed'),
    (r'\bsun myung\b', 'NRM (High-Demand)', 'Unification Church', EXPLICIT, 'sun_myung'),
    (r'\bjehovah.s? witness\b', 'NRM (High-Demand)', "Jehovah's Witnesses", EXPLICIT, 'jw'),
    (r'\bwatchtower\b', 'NRM (High-Demand)', "Jehovah's Witnesses", EXPLICIT, 'watchtower'),
    (r'\bkingdom hall\b', 'NRM (High-Demand)', "Jehovah's Witnesses", STRONG_NAME, 'kingdom_hall'),

    # ── MORMON FUNDAMENTALIST ──
    (r'\bapostolic united brethren\b', 'NRM (Mormon Fund.)', 'Apostolic United Brethren', EXPLICIT, 'aub'),
    (r'\bcovenant of the christ\b', 'NRM (Mormon Fund.)', 'Covenant of the Christ', EXPLICIT, 'covenant_christ'),
    (r'\border of levi\b', 'NRM (Mormon Fund.)', 'Order of Levi', EXPLICIT, 'order_levi'),

    # ── COMMUNAL / INTENTIONAL ──
    (r'\bintentional community\b', 'Communal', 'Intentional Community', GOOD_NAME, 'intentional'),
    (r'\becovillage\b', 'Communal', 'Ecovillage', STRONG_NAME, 'ecovillage'),
    (r'\bcohousing\b', 'Communal', 'Cohousing', STRONG_NAME, 'cohousing'),
]

# ── Exclusion check ──
def is_christian_name(name):
    """Returns True if the name has mainstream Christian markers, meaning it's not NRM."""
    nl = (name or '').lower()
    for pat in CHRISTIAN_EXCLUSIONS:
        if re.search(pat, nl):
            return True
    return False

def classify_nrm(name):
    """Classify NRM type from name. Returns (category, subcategory, confidence, source) or None."""
    nl = (name or '').lower()
    if not nl:
        return None, None, 0, None
    
    for pattern, cat, subcat, conf, src in RULES:
        if re.search(pattern, nl):
            # Exclusion check: only for ambiguous patterns that overlap with Christian names
            # Unambiguous patterns (scientology, wicca, theosophy, etc.) skip this
            if is_christian_name(nl):
                # Ambiguous patterns — skip if name looks Christian
                ambiguous = ('New Thought', 'NeoPagan', 'New Age', 'UFO Religion',
                             'Spiritualist', 'Esoteric')
                if cat in ambiguous:
                    continue
            return cat, subcat, conf, src
    
    return None, None, 0, None


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('nrm_category', 'TEXT'),
        ('nrm_subcategory', 'TEXT'),
        ('nrm_confidence', 'REAL'),
        ('nrm_classification_source', 'TEXT'),
        ('nrm_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def main():
    parser = argparse.ArgumentParser(description='NRM classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    where = '' if args.reprocess else "AND (nrm_category IS NULL OR nrm_category = '')"
    limit = f'LIMIT {args.limit}' if args.limit else ''

    # Target records most likely to be NRM: 'other'/'unknown'/NULL faith_traditions first,
    # then fall back to faith traditions with possible NRM misclassifications
    rows = db.execute(f"""
        SELECT id, name, city, state, faith_tradition, denomination
        FROM churches
        WHERE (faith_tradition IN ('other', 'unknown') OR faith_tradition IS NULL)
          AND (nrm_category IS NULL OR nrm_category = '')
        ORDER BY id
        {limit}
    """).fetchall()

    # Also get records from other faiths that might be misclassified NRM
    rows2 = db.execute(f"""
        SELECT id, name, city, state, faith_tradition, denomination
        FROM churches
        WHERE faith_tradition NOT IN ('other', 'unknown')
          AND faith_tradition IS NOT NULL
          AND (nrm_category IS NULL OR nrm_category = '')
          AND (LOWER(denomination) LIKE '%spiritualist%' OR LOWER(denomination) LIKE '%scientolog%'
               OR LOWER(denomination) LIKE '%unity%' OR LOWER(denomination) LIKE '%theosoph%'
               OR LOWER(name) LIKE '%spiritualist%' OR LOWER(name) LIKE '%scientolog%'
               OR LOWER(name) LIKE '%wicca%' OR LOWER(name) LIKE '%pagan%'
               OR LOWER(name) LIKE '%theosoph%' OR LOWER(name) LIKE '%unity%')
        ORDER BY id
        {limit}
    """).fetchall()

    all_rows = list(rows) + list(rows2)
    # Deduplicate by id
    seen = set()
    unique_rows = []
    for r in all_rows:
        if r[0] not in seen:
            seen.add(r[0])
            unique_rows.append(r)

    print(f'Records to scan for NRM: {len(unique_rows):,}')

    if args.dry_run:
        counts = {}
        matched = 0
        for r in unique_rows[:200]:
            cat, subcat, conf, src = classify_nrm(r[1])
            if cat:
                key = f'{cat} > {subcat}'
                counts[key] = counts.get(key, 0) + 1
                matched += 1
        print(f'\nName match rate: {matched}/{min(200, len(unique_rows))} ({matched*100//min(200, len(unique_rows))}%)')
        print(f'\n{"Category > Subcategory":50s} {"Count":>6s}')
        print('-' * 60)
        for k, c in sorted(counts.items(), key=lambda x: -x[1]):
            print(f'{k:50s} {c:>6,}')
        print(f'\nSample matches:')
        matched = 0
        for r in unique_rows:
            if matched >= 10:
                break
            cat, subcat, conf, src = classify_nrm(r[1])
            if cat:
                print(f'  {r[0]:>8d} | {r[1][:50]:50s} -> {cat} / {subcat} (c={conf:.2f})')
                matched += 1
        db.close()
        return

    # Phase 1: Classify
    matches = 0
    for r in unique_rows:
        cat, subcat, conf, src = classify_nrm(r[1])
        if cat:
            db.execute("""
                UPDATE churches SET
                    nrm_category = ?,
                    nrm_subcategory = ?,
                    nrm_confidence = ?,
                    nrm_classification_source = ?,
                    nrm_updated = datetime('now'),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (cat, subcat, conf, src, r[0]))
            matches += 1
    db.commit()
    print(f'\nClassified: {matches:,} / {len(unique_rows):,}')

    # Report
    db2 = sqlite3.connect(DB_PATH, timeout=60)
    rs = db2.execute("""
        SELECT nrm_category, nrm_subcategory, COUNT(*) as cnt,
               ROUND(AVG(nrm_confidence), 3) as avg_conf
        FROM churches
        WHERE nrm_category IS NOT NULL AND nrm_category != ''
        GROUP BY nrm_category, nrm_subcategory
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Category":25s} {"Subcategory":30s} {"Count":>7s} {"Conf":>6s}')
    print('-' * 72)
    total = 0
    prev_cat = ''
    for r in rs:
        cat_str = r[0] if r[0] != prev_cat else ''
        print(f'{cat_str:25s} {r[1]:30s} {r[2]:>7,} {r[3]:>6.2f}')
        total += r[2]
        prev_cat = r[0]
    print(f'\nTotal NRM records classified: {total:,}')

    # Faith tradition cross-tab
    print()
    print("=== CROSS-TAB: faith_tradition × NRM category ===")
    rs = db2.execute("""
        SELECT COALESCE(faith_tradition,'NULL'), nrm_category, COUNT(*)
        FROM churches
        WHERE nrm_category IS NOT NULL AND nrm_category != ''
        GROUP BY faith_tradition, nrm_category
        ORDER BY COUNT(*) DESC
        LIMIT 20
    """).fetchall()
    for r in rs:
        print(f'  {r[0]:15s} × {r[1]:25s} {r[2]:>6,}')

    db2.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

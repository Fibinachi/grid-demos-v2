#!/usr/bin/env python3
"""
Buddhist Tradition Classification
==================================
Classifies Buddhist temples and organizations by tradition using
name patterns and website content signals.

Traditions:
  - Zen (Soto/Rinzai)
  - Tibetan (Vajrayana — Gelug/Kagyu/Nyingma/Sakya)
  - Theravada (Southeast Asian)
  - Nichiren (SGI/Lotus Sutra)
  - Pure Land (Jodo Shin/Shin/Shingon/Amida)
  - Vipassana / Insight Meditation
  - Generic (Buddhist/Buddha/Dharma/Sangha)

Premium API: This classifier powers a paid API endpoint.
Output includes: buddhist_tradition, buddhist_confidence

Usage:
    python scripts/enrichment/classify_buddhist.py
    python scripts/enrichment/classify_buddhist.py --dry-run
    python scripts/enrichment/classify_buddhist.py --reprocess
    python scripts/enrichment/classify_buddhist.py --limit 100
    python scripts/enrichment/classify_buddhist.py --website 50
"""
import argparse
import re
import sqlite3
import os
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# ── Confidence thresholds ──
EXPLICIT = 0.95
STRONG_NAME = 0.80
GOOD_NAME = 0.70
MODERATE = 0.60
WEAK = 0.40

# ═══════════════════════════════════════════════════════════════════
# BUDDHIST KEYWORDS — ordered by specificity
# ═══════════════════════════════════════════════════════════════════

# Format: (regex_pattern, tradition, confidence, source_tag)

ZEN_RULES = [
    (r'\bzen\b', 'Zen', STRONG_NAME, 'zen_simple'),
    (r'\bzendo\b', 'Zen', EXPLICIT, 'zendo'),
    (r'\bsoto\s', 'Zen (Soto)', EXPLICIT, 'soto'),
    (r'\brinzai\b', 'Zen (Rinzai)', EXPLICIT, 'rinzai'),
    (r'\broshi\b', 'Zen', STRONG_NAME, 'roshi'),
    (r'\bsanzen\b', 'Zen', EXPLICIT, 'sanzen'),
    (r'\bkoan\b', 'Zen', STRONG_NAME, 'koan'),
    (r'\bthich\b', 'Zen (Thien)', STRONG_NAME, 'thich'),
]

TIBETAN_RULES = [
    (r'\btibetan\b', 'Tibetan (Vajrayana)', GOOD_NAME, 'tibetan_keyword'),
    (r'\bvajrayana\b', 'Tibetan (Vajrayana)', EXPLICIT, 'vajrayana'),
    (r'\blama\b', 'Tibetan (Vajrayana)', GOOD_NAME, 'lama'),
    (r'\brinpoche\b', 'Tibetan (Vajrayana)', EXPLICIT, 'rinpoche'),
    (r'\b(gyalwa|karmapa|dalai.lama)\b', 'Tibetan (Vajrayana)', EXPLICIT, 'tibetan_title'),
    (r'\bgelug\b', 'Tibetan (Gelug)', EXPLICIT, 'gelug'),
    (r'\bkagyu\b', 'Tibetan (Kagyu)', EXPLICIT, 'kagyu'),
    (r'\bnyingma\b', 'Tibetan (Nyingma)', EXPLICIT, 'nyingma'),
    (r'\bsakya\b', 'Tibetan (Sakya)', EXPLICIT, 'sakya'),
    (r'\bdzogchen\b', 'Tibetan (Nyingma)', EXPLICIT, 'dzogchen'),
    (r'\bmahamudra\b', 'Tibetan (Kagyu)', EXPLICIT, 'mahamudra'),
    (r'\bchogyam\b', 'Tibetan (Kagyu)', EXPLICIT, 'chogyam'),
    (r'\btulku\b', 'Tibetan (Vajrayana)', EXPLICIT, 'tulku'),
    (r'\bmandala\s+(center|foundation|society)\b', 'Tibetan (Vajrayana)', MODERATE, 'mandala'),
    (r'\bshedra\b', 'Tibetan (Vajrayana)', EXPLICIT, 'shedra'),
    (r'\bmonastic\s+(college|retreat|center|community)\b', 'Tibetan (Vajrayana)', MODERATE, 'monastic'),
]

THERAVADA_RULES = [
    (r'\btheravada\b', 'Theravada', EXPLICIT, 'theravada_keyword'),
    (r'\bwat\s', 'Theravada (Thai)', STRONG_NAME, 'wat_thai'),
    (r'\bvihara\b', 'Theravada', GOOD_NAME, 'vihara'),
    (r'\bvipassana\b', 'Theravada (Vipassana)', STRONG_NAME, 'vipassana'),
    (r'\bmahasi\b', 'Theravada (Mahasi)', EXPLICIT, 'mahasi'),
    (r'\bburmese\b', 'Theravada (Burmese)', STRONG_NAME, 'burmese'),
    (r'\bthai\s+(buddhist|temple|monastery|center)\b', 'Theravada (Thai)', STRONG_NAME, 'thai_buddhist'),
    (r'\blao\b', 'Theravada (Lao)', STRONG_NAME, 'lao'),
    (r'\blaotian\b', 'Theravada (Lao)', STRONG_NAME, 'laotian'),
    (r'\bsri\s+lanka\b', 'Theravada (Sri Lankan)', STRONG_NAME, 'sri_lankan'),
    (r'\bsinghalese\b', 'Theravada (Sri Lankan)', STRONG_NAME, 'singhalese'),
    (r'\bcambodian\b', 'Theravada (Cambodian)', STRONG_NAME, 'cambodian'),
    (r'\bkhmer\b', 'Theravada (Cambodian)', STRONG_NAME, 'khmer'),
    (r'\bmyanmar\b', 'Theravada (Burmese)', STRONG_NAME, 'myanmar'),
    (r'\bforest\s+(monastery|sangha|tradition|temple)\b', 'Theravada (Forest)', STRONG_NAME, 'forest_tradition'),
    (r'\bajahn?\b', 'Theravada (Forest)', EXPLICIT, 'ajahn'),
    (r'\bbhikkhu\b', 'Theravada', STRONG_NAME, 'bhikkhu'),
]

NICHIREN_RULES = [
    (r'\bnichiren\b', 'Nichiren', EXPLICIT, 'nichiren_keyword'),
    (r'\bsgi\b', 'Nichiren (SGI)', EXPLICIT, 'sgi'),
    (r'\bsoka.gakkai\b', 'Nichiren (SGI)', EXPLICIT, 'soka_gakkai'),
    (r'\blotus.sutra\b', 'Nichiren', STRONG_NAME, 'lotus_sutra'),
    (r'\bdaisaku.ikeda\b', 'Nichiren (SGI)', EXPLICIT, 'ikeda'),
    (r'\bgohonzon\b', 'Nichiren', EXPLICIT, 'gohonzon'),
    (r'\bnam.myoho.renge.kyo\b', 'Nichiren', EXPLICIT, 'daimoku'),
    (r'\bnichiren.shu\b', 'Nichiren', EXPLICIT, 'nichiren_shu'),
]

PURE_LAND_RULES = [
    (r'\bjodo\b', 'Pure Land (Jodo)', EXPLICIT, 'jodo'),
    (r'\bjōdo\b', 'Pure Land (Jodo)', EXPLICIT, 'jodo_unicode'),
    (r'\bshin\s+(buddhist|temple|center|sangha|church)\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'shin_buddhist'),
    (r'\bamida\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'amida'),
    (r'\bamitabha\b', 'Pure Land', EXPLICIT, 'amitabha'),
    (r'\bshingon\b', 'Pure Land (Shingon)', EXPLICIT, 'shingon'),
    (r'\bhonpa\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'honpa'),
    (r'\bnishi.hongwanji\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'nishi_hongwanji'),
    (r'\bhigashi.hongwanji\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'higashi_hongwanji'),
    (r'\bjodo.shinshu\b', 'Pure Land (Jodo Shinshu)', EXPLICIT, 'jodo_shinshu'),
]

VIPASSANA_INSIGHT_RULES = [
    (r'\bvipassana\b', 'Vipassana', STRONG_NAME, 'vipassana_keyword'),
    (r'\binsight.meditation\b', 'Vipassana (Insight)', EXPLICIT, 'insight_meditation'),
    (r'\bims\b', 'Vipassana (IMS)', EXPLICIT, 'ims'),
    (r'\bdharma.center\b', 'Vipassana', MODERATE, 'dharma_center'),
    (r'\bspirit.rock\b', 'Vipassana (Insight)', EXPLICIT, 'spirit_rock'),
    (r'\bgat[e]?\s+in\s+gate\b', 'Vipassana', EXPLICIT, 'gate_gate'),
    (r'\bg.oy.k\b', 'Vipassana (Goenka)', EXPLICIT, 'goenka'),
    (r'\bs.n.goenka\b', 'Vipassana (Goenka)', EXPLICIT, 'sn_goenka'),
]

GENERIC_RULES = [
    (r'\bbuddhist\s+(temple|center|society|congregation|church|association|monastery|foundation)\b', 'Buddhist (Generic)', MODERATE, 'buddhist_org'),
    (r'\bbuddhist\b', 'Buddhist (Generic)', WEAK, 'buddhist_keyword'),
    (r'\bbuddha\s+(temple|center|society|statue|monastery|foundation|memorial)\b', 'Buddhist (Generic)', MODERATE, 'buddha_org'),
    (r'\bbuddha\b', 'Buddhist (Generic)', WEAK, 'buddha_keyword'),
    (r'\bdharma\s+(center|foundation|society|temple|association)\b', 'Buddhist (Generic)', MODERATE, 'dharma_org'),
    (r'\bdharma\b', 'Buddhist (Generic)', WEAK, 'dharma_keyword'),
    (r'\bsangha\b', 'Buddhist (Generic)', MODERATE, 'sangha'),
    (r'\bstupa\b', 'Buddhist (Generic)', STRONG_NAME, 'stupa'),
]

# ── Website content signals ──
WEBSITE_SIGNALS = {
    'zen': [r'\bzen\b', r'\bzazen\b', r'\bsoto\b', r'\brinzai\b', r'\bteisho\b'],
    'tibetan': [r'\btibetan\b', r'\bvajrayana\b', r'\bmandala\b', r'\bdeity.yoga\b', r'\bphowa\b'],
    'theravada': [r'\btheravada\b', r'\bbhikkhu\b', r'\bcitta\b', r'\babhidhamma\b', r'\bmetta\b'],
    'nichiren': [r'\bnichiren\b', r'\bgohonzon\b', r'\bdaimoku\b', r'\bmyoho.renge.kyo\b'],
    'pure_land': [r'\bamida\b', r'\bjodo\b', r'\bshingon\b', r'\bhongwanji\b', r'\bshin\s+buddhist\b'],
    'vipassana': [r'\bvipassana\b', r'\bsatipatthana\b', r'\banapana\b'],
}


# ═══════════════════════════════════════════════════════════════════
# CLASSIFIER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def classify_buddhist(name, website_text=""):
    """Classify Buddhist tradition from name + optional website text."""
    text = f"{name} {website_text}".lower() if website_text else (name or '').lower()
    if not text:
        return "buddhist_unknown", 0, None

    for rules, default in [
        (ZEN_RULES, None),
        (TIBETAN_RULES, None),
        (THERAVADA_RULES, None),
        (NICHIREN_RULES, None),
        (PURE_LAND_RULES, None),
        (VIPASSANA_INSIGHT_RULES, None),
        (GENERIC_RULES, None),
    ]:
        for pattern, trad, conf, src in rules:
            if re.search(pattern, text):
                return (trad if trad else default), conf, src

    return "buddhist_unknown", 0, None


def classify_by_name(name):
    """Name-only classifier wrapper."""
    return classify_buddhist(name)


def classify_by_website(url):
    """Website content classifier."""
    if not url:
        return None, 0, None
    url = url.strip()
    if not url.startswith('http'):
        url = 'http://' + url
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(100000).decode('utf-8', 'replace')
    except Exception:
        return None, 0, None
    html_lower = html.lower()
    for trad, patterns in WEBSITE_SIGNALS.items():
        for pat in patterns:
            if re.search(pat, html_lower):
                return trad, STRONG_NAME, f'website_{trad}'
    return None, 0, None


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('buddhist_tradition', 'TEXT'),
        ('buddhist_confidence', 'REAL'),
        ('buddhist_classification_source', 'TEXT'),
        ('buddhist_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def main():
    parser = argparse.ArgumentParser(description='Buddhist tradition classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--website', type=int, default=0, help='Scrape N websites')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    where = '' if args.reprocess else "AND (buddhist_tradition IS NULL OR buddhist_tradition = '')"
    limit = f'LIMIT {args.limit}' if args.limit else ''
    rows = db.execute(f"""
        SELECT id, name, city, state, website
        FROM churches
        WHERE faith_tradition = 'buddhist'
        {where}
        ORDER BY id
        {limit}
    """).fetchall()

    print(f'Buddhist records to classify: {len(rows):,}')

    if args.dry_run:
        counts = {}
        for r in rows[:50]:
            trad, conf, src = classify_by_name(r[1])
            if trad:
                counts[trad] = counts.get(trad, 0) + 1
        print(f'\n{"Tradition":30s} {"Count":>6s}')
        print('-' * 40)
        for t, c in sorted(counts.items(), key=lambda x: -x[1]):
            print(f'{t:30s} {c:>6,}')
        print(f'\nSample (first 5):')
        for r in rows[:5]:
            trad, conf, src = classify_by_name(r[1])
            print(f'  {r[0]:>8d} | {r[1][:50]:50s} -> {trad or "no match":30s}')
        db.close()
        return

    # Phase 1: Name heuristic
    name_matches = 0
    for r in rows:
        trad, conf, src = classify_by_name(r[1])
        if trad != 'buddhist_unknown':
            db.execute("""
                UPDATE churches SET
                    buddhist_tradition = ?,
                    buddhist_confidence = ?,
                    buddhist_classification_source = ?,
                    buddhist_updated = datetime('now'),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (trad, conf, src, r[0]))
            name_matches += 1
    db.commit()
    print(f'\nPhase 1 — Name heuristic: {name_matches:,} / {len(rows):,} matched')

    # Report
    rs = db.execute("""
        SELECT buddhist_tradition, COUNT(*) as cnt,
               ROUND(AVG(buddhist_confidence), 3) as avg_conf
        FROM churches
        WHERE buddhist_tradition != '' AND buddhist_tradition IS NOT NULL
        GROUP BY buddhist_tradition
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Tradition":30s} {"Count":>7s} {"Avg Conf":>8s}')
    print('-' * 50)
    total = 0
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,} {r[2]:>8.3f}')
        total += r[1]

    rs = db.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith_tradition = 'buddhist'
        AND (buddhist_tradition IS NULL OR buddhist_tradition = '')
    """).fetchone()
    print(f'\nTotal classified: {total:,}')
    print(f'Still unclassified: {rs[0]:,}')

    rs = db.execute("""
        SELECT buddhist_classification_source, COUNT(*) as cnt
        FROM churches WHERE buddhist_classification_source != ''
        GROUP BY buddhist_classification_source
        ORDER BY cnt DESC LIMIT 15
    """).fetchall()
    print(f'\n{"Source":30s} {"Count":>7s}')
    print('-' * 40)
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

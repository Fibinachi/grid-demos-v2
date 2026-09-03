#!/usr/bin/env python3
"""
Hindu Sub-Tradition Classification
===================================
Classifies Hindu temples and organizations by sampradaya (tradition)
and regional origin using name + website content signals.

Traditions:
  - Vaishnav (Vishnu/Krishna/Rama worship — largest globally)
  - Shaivite (Shiva worship)
  - Shakta (Devi/Durga/Kali worship)
  - Swaminarayan (Gujarati bhakti tradition)
  - ISKCON (Gaudiya Vaishnava — Hare Krishna)
  - South Indian (Tamil/Telugu/Kerala temple naming)
  - North Indian (Hindi-belt naming conventions)

Premium API: This classifier powers a paid API endpoint.
Output includes: hindu_affiliation, hindu_confidence, hindu_region

Usage:
    python scripts/enrichment/classify_hindu.py
    python scripts/enrichment/classify_hindu.py --dry-run
    python scripts/enrichment/classify_hindu.py --reprocess
    python scripts/enrichment/classify_hindu.py --limit 100
    python scripts/enrichment/classify_hindu.py --website 50   # Scrape N sites
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
MODERATE = 0.55
ETHNIC = 0.40
REGIONAL = 0.35

# ═══════════════════════════════════════════════════════════════════
# HINDU NAME KEYWORDS — Ordered by specificity (highest first)
# ═══════════════════════════════════════════════════════════════════

# Each rule: (pattern_list, affiliation, confidence, source_tag)

SWAMINARAYAN_RULES = [
    (r'\bswaminarayan\b', 'Swaminarayan', EXPLICIT, 'swaminarayan_name'),
    (r'\bbaps\b', 'Swaminarayan (BAPS)', EXPLICIT, 'baps_name'),
    (r'\bbochasanwasi\b', 'Swaminarayan (BAPS)', EXPLICIT, 'baps_bochasan'),
    (r'\bakshar.purushottam\b', 'Swaminarayan (BAPS)', EXPLICIT, 'baps_akshar'),
    (r'\bloyadham\b', 'Swaminarayan', STRONG_NAME, 'loyadham'),
    (r'\bvasna\s+sanstha\b', 'Swaminarayan (Vasna)', EXPLICIT, 'vasna_sanstha'),
    (r'\bsahajanand\b', 'Swaminarayan', EXPLICIT, 'sahajanand'),
    (r'\bagyna.upasana\b', 'Swaminarayan', STRONG_NAME, 'agyna_upasana'),
]

ISKCON_RULES = [
    (r'\biskcon\b', 'ISKCON', EXPLICIT, 'iskcon_name'),
    (r'\bkrishna.consciousness\b', 'ISKCON', EXPLICIT, 'krishna_consciousness'),
    (r'\bkrishnafest\b', 'ISKCON', EXPLICIT, 'krishnafest'),
    (r'\bhare.krishna\b', 'ISKCON', EXPLICIT, 'hare_krishna'),
    (r'\bgaudiya\b', 'ISKCON', STRONG_NAME, 'gaudiya'),
    (r'\bgour.nitai\b', 'ISKCON', STRONG_NAME, 'gour_nitai'),
    (r'\bsri.sri.gour\b', 'ISKCON', STRONG_NAME, 'sri_gour'),
    (r'\bnitai\b', 'ISKCON', MODERATE, 'nitai'),
    (r'\bprabhupad\b', 'ISKCON', EXPLICIT, 'prabhupad'),
    (r'\b(rgveda|krishna)\s*base\b', 'ISKCON', MODERATE, 'krishna_base'),
    (r'\bvedic\s+way\b', 'ISKCON', MODERATE, 'vedic_way'),
]

VAISHNAV_RULES = [
    # Sri Vaishnava (Ramanuja) — South Indian
    (r'\bsri.vaishnava\b', 'Vaishnav (Sri)', EXPLICIT, 'sri_vaishnava'),
    (r'\bramanuja\b', 'Vaishnav (Sri)', EXPLICIT, 'ramanuja'),
    (r'\b(ahobilam|parakala|sri\s+rangam)\b', 'Vaishnav (Sri)', STRONG_NAME, 'sri_vaishnava_temple'),
    # Vishnu temples
    (r'\bvishnu\s+mandir\b', 'Vaishnav', STRONG_NAME, 'vishnu_mandir'),
    (r'\bshri.vishnu\b', 'Vaishnav', STRONG_NAME, 'shri_vishnu'),
    # Krishna temples
    (r'\bradha.*krishna\b', 'Vaishnav (Krishna)', STRONG_NAME, 'radha_krishna'),
    (r'\bradhe\b', 'Vaishnav (Krishna)', GOOD_NAME, 'radhe'),
    (r'\bradha.raman\b', 'Vaishnav (Krishna)', STRONG_NAME, 'radha_raman'),
    (r'\bgovind[a]?\b', 'Vaishnav (Krishna)', GOOD_NAME, 'govinda'),
    (r'\bgop[ae]l[a]?\b', 'Vaishnav (Krishna)', GOOD_NAME, 'gopala'),
    (r'\bmadhav?\b', 'Vaishnav (Krishna)', MODERATE, 'madhav'),
    # Rama temples
    (r'\bram[a]?\s+mandir\b', 'Vaishnav (Rama)', STRONG_NAME, 'rama_mandir'),
    (r'\bshri.ram\b', 'Vaishnav (Rama)', GOOD_NAME, 'shri_ram'),
    (r'\bsitaram\b', 'Vaishnav (Rama)', STRONG_NAME, 'sitaram'),
    (r'\bramayan[a]?\b', 'Vaishnav (Rama)', MODERATE, 'ramayana'),
    # Lakshmi Narayan (Vaishnav)
    (r'\blakshmi.*narayan\b', 'Vaishnav', STRONG_NAME, 'lakshmi_narayan'),
    (r'\blaxmi.*narayan\b', 'Vaishnav', STRONG_NAME, 'laxmi_narayan'),
    (r'\bnarayan\s+mandir\b', 'Vaishnav', STRONG_NAME, 'narayan_mandir'),
    # Venkateswara / Balaji (Tirupati — South Indian Vaishnav)
    (r'\bvenkateswara\b', 'Vaishnav (Venkateswara)', STRONG_NAME, 'venkateswara'),
    (r'\bvenkatesh\b', 'Vaishnav (Venkateswara)', GOOD_NAME, 'venkatesh'),
    (r'\bbalaji\b', 'Vaishnav (Venkateswara)', MODERATE, 'balaji'),
    (r'\btirupati\b', 'Vaishnav (Venkateswara)', GOOD_NAME, 'tirupati'),
    # Satya Narayan
    (r'\bsatya.narayan\b', 'Vaishnav', STRONG_NAME, 'satya_narayan'),
    (r'\bsurya.narayan\b', 'Vaishnav', STRONG_NAME, 'surya_narayan'),
]

SHAIVITE_RULES = [
    (r'\bshiva\s+mandir\b', 'Shaivite', STRONG_NAME, 'shiva_mandir'),
    (r'\bshiv\s+mandir\b', 'Shaivite', STRONG_NAME, 'shiv_mandir'),
    (r'\bmaha.shiva\b', 'Shaivite', STRONG_NAME, 'maha_shiva'),
    (r'\bmahadev\b', 'Shaivite', STRONG_NAME, 'mahadev'),
    (r'\bneelkanth\b', 'Shaivite', STRONG_NAME, 'neelkanth'),
    (r'\brudra\b', 'Shaivite', STRONG_NAME, 'rudra'),
    (r'\bshankar[a]?\b', 'Shaivite', GOOD_NAME, 'shankar'),
    (r'\b(shiva|siva)\b', 'Shaivite', MODERATE, 'shiva_generic'),
    (r'\b(shiv|shivji)\b', 'Shaivite', MODERATE, 'shiv_generic'),
    (r'\bgang[a]?\s+(mandir|temple)\b', 'Shaivite', GOOD_NAME, 'ganga_temple'),
    (r'\bjyotirling[a]?\b', 'Shaivite', EXPLICIT, 'jyotirling'),
    (r'\bnataraj[a]?\b', 'Shaivite', STRONG_NAME, 'nataraja'),
    (r'\bling[a]m\b', 'Shaivite', EXPLICIT, 'lingam'),
    (r'\bpashupati\b', 'Shaivite', EXPLICIT, 'pashupati'),
    (r'\bka[ai]lash\b', 'Shaivite', MODERATE, 'kailash'),
    (r'\bbholenath\b', 'Shaivite', STRONG_NAME, 'bholenath'),
    (r'\bshankara\b', 'Shaivite', EXPLICIT, 'shankara'),
    (r'\bkashmir\s+shaivite\b', 'Shaivite (Kashmiri)', EXPLICIT, 'kashmir_shaivite'),
]

SHAKTA_RULES = [
    (r'\bdurga\s+mandir\b', 'Shakta (Durga)', STRONG_NAME, 'durga_mandir'),
    (r'\bdurga\b', 'Shakta (Durga)', MODERATE, 'durga_name'),
    (r'\bkali\s+mandir\b', 'Shakta (Kali)', STRONG_NAME, 'kali_mandir'),
    (r'\bdevi\s+mandir\b', 'Shakta', STRONG_NAME, 'devi_mandir'),
    (r'\bshri.devi\b', 'Shakta', STRONG_NAME, 'shri_devi'),
    (r'\bshakti\b', 'Shakta', GOOD_NAME, 'shakti'),
    (r'\badishakti\b', 'Shakta', EXPLICIT, 'adishakti'),
    (r'\bchandi\b', 'Shakta', EXPLICIT, 'chandi'),
    (r'\bbhagavati\b', 'Shakta', EXPLICIT, 'bhagavati'),
    (r'\bamman\b', 'Shakta (Amman)', STRONG_NAME, 'amman'),
    (r'\bkamaksh[iy]?\b', 'Shakta', EXPLICIT, 'kamakshi'),
    (r'\blalitha?\b', 'Shakta', STRONG_NAME, 'lalitha'),
    (r'\bsarveshwari\b', 'Shakta', EXPLICIT, 'sarveshwari'),
    (r'\bmaha.kali\b', 'Shakta (Kali)', EXPLICIT, 'maha_kali'),
    (r'\bsiddha.lalitha\b', 'Shakta', EXPLICIT, 'siddha_lalitha'),
]

GANESH_RULES = [
    (r'\bganesh\s+mandir\b', 'Shaivite (Ganesh)', STRONG_NAME, 'ganesh_mandir'),
    (r'\bganesh\b', 'Shaivite (Ganesh)', MODERATE, 'ganesh_name'),
    (r'\bvighneshwar?\b', 'Shaivite (Ganesh)', STRONG_NAME, 'vighneshwar'),
    (r'\bganapati\b', 'Shaivite (Ganesh)', STRONG_NAME, 'ganapati'),
    (r'\bpillaiyar\b', 'Shaivite (Ganesh)', STRONG_NAME, 'pillaiyar'),
    (r'\bsiddhivinayak\b', 'Shaivite (Ganesh)', STRONG_NAME, 'siddhivinayak'),
]

AYYAPPA_RULES = [
    (r'\bayyappa\b', "Vaishnav (Ayyappa)", STRONG_NAME, 'ayyappa'),
    (r'\bsabari\b', "Vaishnav (Ayyappa)", GOOD_NAME, 'sabari'),
    (r'\b(subrahmanya|murugan|karthikeya|shastha)\b', 'Shaivite (Murugan)', STRONG_NAME, 'murugan'),
]

HANUMAN_RULES = [
    (r'\bhanuman\b', 'Vaishnav (Hanuman)', MODERATE, 'hanuman'),
    (r'\bsankat.mochan\b', 'Vaishnav (Hanuman)', STRONG_NAME, 'sankat_mochan'),
    (r'\bbajrang\b', 'Vaishnav (Hanuman)', STRONG_NAME, 'bajrang'),
]

SAI_BABA_RULES = [
    (r'\bsai.baba\b', 'Sai Baba', EXPLICIT, 'sai_baba'),
    (r'\bshirdi\b', 'Sai Baba', STRONG_NAME, 'shirdi'),
    (r'\bsai\s+(mandir|temple|center|foundation)\b', 'Sai Baba', STRONG_NAME, 'sai_name'),
]

OTHER_SECTS_RULES = [
    (r'\bchinmaya\b', 'Chinmaya Mission', EXPLICIT, 'chinmaya'),
    (r'\barya.samaj\b', 'Arya Samaj', EXPLICIT, 'arya_samaj'),
    (r'\bramakrishna\b', 'Ramakrishna Mission', EXPLICIT, 'ramakrishna'),
    (r'\bvivekananda\b', 'Ramakrishna Mission', EXPLICIT, 'vivekananda'),
    (r'\bvedanta\s+(society|center|mission)\b', 'Ramakrishna Mission', STRONG_NAME, 'vedanta_society'),
    (r'\bsivananda\b', 'Sivananda Yoga', EXPLICIT, 'sivananda'),
    (r'\bbrahma.kumaris?\b', 'Brahma Kumaris', EXPLICIT, 'brahma_kumaris'),
    (r'\bsaty[ae]\s+sai\b', 'Sathya Sai Baba', EXPLICIT, 'sathya_sai'),
    (r'\bma\s+anandamayee\b', 'Shakta (Anandamayee)', EXPLICIT, 'anandamayee'),
    (r'\bnikhil\s+gang[a]?\b', 'Nikhil Ganga', EXPLICIT, 'nikhil_ganga'),
    (r'\bsri.aurobindo\b', 'Aurobindo', EXPLICIT, 'aurobindo'),
    (r'\b(brahma|prajapati)\s+(sama[jj]|association)\b', 'Arya Samaj', MODERATE, 'brahma_samaj'),
    (r'\bsanat?an\b', 'Sanatan Dharma', MODERATE, 'sanatan'),
    (r'\bdivya.jyoti\b', 'Divya Jyoti', EXPLICIT, 'divya_jyoti'),
    (r'\bgayatri\s+(parivar|foundation|mandir)\b', 'Gayatri Parivar', EXPLICIT, 'gayatri_parivar'),
    (r'\bgayatri\b', 'Gayatri Parivar', MODERATE, 'gayatri'),
]

# ── Regional Rules (applied as secondary tags) ──
REGION_RULES = [
    # Tamil / South Indian
    (r'\b(kovil|koil)\b', 'South (Tamil)', 'tamil_kovil'),
    (r'\btamil\b', 'South (Tamil)', 'tamil_name'),
    (r'\bmalayali\b', 'South (Kerala)', 'malayali'),
    (r'\bmalayalam\b', 'South (Kerala)', 'malayalam'),
    (r'\bkerela\b', 'South (Kerala)', 'kerala'),
    (r'\bkerala\b', 'South (Kerala)', 'kerala'),
    (r'\bmalayalee\b', 'South (Kerala)', 'malayalee'),
    # Telugu / Andhra
    (r'\b(andhra|telugu)\b', 'South (Telugu)', 'telugu'),
    (r'\btirupati\b', 'South (Telugu)', 'tirupati'),
    (r'\bvenkateswara\b', 'South (Telugu)', 'venkateswara'),
    # Kannada
    (r'\bkannada\b', 'South (Kannada)', 'kannada'),
    (r'\bkarnataka\b', 'South (Kannada)', 'karnataka'),
    # Bengali
    (r'\bbengali\b', 'East (Bengali)', 'bengali'),
    (r'\bbangladesh\b', 'East (Bengali)', 'bangladesh'),
    # Gujarati
    (r'\bgujarati\b', 'West (Gujarati)', 'gujarati'),
    (r'\bpatidar\b', 'West (Gujarati)', 'patidar'),
    # Punjabi
    (r'\bpunjabi\b', 'North (Punjabi)', 'punjabi'),
    (r'\bpunjab\b', 'North (Punjabi)', 'punjab'),
    # Sindhi
    (r'\bsindhi\b', 'North (Sindhi)', 'sindhi'),
    # Nepali
    (r'\bnepal[i]?\b', 'North (Nepali)', 'nepali'),
]

# ── Website keyword signals ──
WEBSITE_SIGNALS = {
    'vaishnav': [
        r'\bvaishnava\b', r'\bvaishnav\b', r'\bvaishnavism\b',
        r'\brama\s+bhakti\b', r'\bkrishna\s+bhakti\b',
    ],
    'shaivite': [
        r'\bshaiva\b', r'\bshaivism\b', r'\bshaivite\b',
        r'\bshiva\s+bhakti\b', r'\bshiva\s+rathri\b',
    ],
    'shakta': [
        r'\bshakta\b', r'\bshaktism\b', r'\bdevi\s+bhakti\b',
        r'\bdurga\s+puja\b', r'\bnavaratri\b',
    ],
    'swaminarayan': [
        r'\bswaminarayan\b', r'\bbaps\b', r'\bhome\s+of\s+god\b',
        r'\bpramukh\s+swami\b', r'\bmahant\s+swami\b',
    ],
    'iskcon': [
        r'\biskcon\b', r'\bkrishna\s+consciousness\b',
        r'\bsrila\s+prabhupada\b', r'\bgaudiya\s+math\b',
    ],
}


# ═══════════════════════════════════════════════════════════════════
# CLASSIFIER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def classify_by_name(name):
    """Classify Hindu sub-tradition from name. Returns (affiliation, region, confidence, source)."""
    nl = (name or '').lower()
    if not nl:
        return None, None, 0, None

    # Ordered by specificity
    for rules, default_aff in [
        (SWAMINARAYAN_RULES, None),
        (ISKCON_RULES, None),
        (SAI_BABA_RULES, None),
        (SHAKTA_RULES, None),
        (SHAIVITE_RULES, None),
        (VAISHNAV_RULES, None),
        (AYYAPPA_RULES, None),
        (GANESH_RULES, None),
        (HANUMAN_RULES, None),
        (OTHER_SECTS_RULES, None),
    ]:
        for pattern, aff, conf, src in rules:
            if re.search(pattern, nl):
                return aff if aff else default_aff, None, conf, src

    return None, None, 0, None


def classify_region(name):
    """Classify regional origin from name. Returns (region_label, confidence, source)."""
    nl = (name or '').lower()
    if not nl:
        return None, 0, None

    for pattern, region, source in REGION_RULES:
        if re.search(pattern, nl):
            return region, REGIONAL, source

    return None, 0, None


def infer_region_from_affiliation(affiliation):
    """Infer region from affiliation when name gives no region signal."""
    if not affiliation:
        return None
    aff_lower = affiliation.lower()
    south_hints = ['venkateswara', 'ayyappa', 'murugan', 'pillaiyar',
                   'sri vaishnava', 'ramanuja', 'amman', 'kamakshi']
    for hint in south_hints:
        if hint in aff_lower:
            return 'South (Inferred)'
    return None


def classify_by_website(url):
    """Website content classifier. Returns (affiliation, confidence, source)."""
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
    for aff, patterns in WEBSITE_SIGNALS.items():
        for pat in patterns:
            if re.search(pat, html_lower):
                return aff, STRONG_NAME, f'website_{aff}'
    return None, 0, None


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('hindu_affiliation', 'TEXT'),
        ('hindu_region', 'TEXT'),
        ('hindu_confidence', 'REAL'),
        ('hindu_classification_source', 'TEXT'),
        ('hindu_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def main():
    parser = argparse.ArgumentParser(description='Hindu sub-tradition classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--website', type=int, default=0, help='Scrape N websites for signals')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    where = '' if args.reprocess else "AND (hindu_affiliation IS NULL OR hindu_affiliation = '')"
    limit = f'LIMIT {args.limit}' if args.limit else ''
    rows = db.execute(f"""
        SELECT id, name, city, state, website
        FROM churches
        WHERE faith_tradition = 'hindu'
        {where}
        ORDER BY id
        {limit}
    """).fetchall()

    print(f'Hindu records to classify: {len(rows):,}')

    if args.dry_run:
        counts = {}
        region_counts = {}
        for r in rows[:50]:
            aff, region, conf, src = classify_by_name(r[1])
            if aff:
                counts[aff] = counts.get(aff, 0) + 1
            reg, reg_conf, reg_src = classify_region(r[1])
            if reg:
                region_counts[reg] = region_counts.get(reg, 0) + 1

        print(f'\n{"Affiliation":30s} {"Count":>6s}')
        print('-' * 40)
        for a, c in sorted(counts.items(), key=lambda x: -x[1]):
            print(f'{a:30s} {c:>6,}')
        print(f'\n{"Region":30s} {"Count":>6s}')
        print('-' * 40)
        for r, c in sorted(region_counts.items(), key=lambda x: -x[1]):
            print(f'{r:30s} {c:>6,}')
        print(f'\nSample (first 5):')
        for r in rows[:5]:
            aff, reg, conf, src = classify_by_name(r[1])
            reg2, _, _ = classify_region(r[1])
            region_str = f' [{reg2}]' if reg2 else ''
            aff_str = aff or 'no match'
            print(f'  {r[0]:>8d} | {r[1][:50]:50s} -> {aff_str:30s}{region_str}')
        db.close()
        return

    # Phase 1: Name heuristic
    name_matches = 0
    for r in rows:
        aff, region, conf, src = classify_by_name(r[1])
        if aff:
            reg, reg_conf, reg_src = classify_region(r[1])
            if not reg:
                reg = infer_region_from_affiliation(aff)
            db.execute("""
                UPDATE churches SET
                    hindu_affiliation = ?,
                    hindu_region = ?,
                    hindu_confidence = ?,
                    hindu_classification_source = ?,
                    hindu_updated = datetime('now'),
                    last_updated = datetime('now')
                WHERE id = ?
            """, (aff, reg, conf, src, r[0]))
            name_matches += 1
    db.commit()
    print(f'\nPhase 1 — Name heuristic: {name_matches:,} / {len(rows):,} matched')
    db.close()

    # Report
    db = sqlite3.connect(DB_PATH, timeout=60)
    rs = db.execute("""
        SELECT hindu_affiliation, COUNT(*) as cnt,
               ROUND(AVG(hindu_confidence), 3) as avg_conf
        FROM churches
        WHERE hindu_affiliation != '' AND hindu_affiliation IS NOT NULL
        GROUP BY hindu_affiliation
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Affiliation":30s} {"Count":>7s} {"Avg Conf":>8s}')
    print('-' * 50)
    total = 0
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,} {r[2]:>8.3f}')
        total += r[1]

    rs = db.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith_tradition = 'hindu'
        AND (hindu_affiliation IS NULL OR hindu_affiliation = '')
    """).fetchone()
    print(f'\nTotal classified: {total:,}')
    print(f'Still unclassified: {rs[0]:,}')

    rs = db.execute("""
        SELECT hindu_region, COUNT(*) as cnt
        FROM churches WHERE hindu_region != '' AND hindu_region IS NOT NULL
        GROUP BY hindu_region ORDER BY cnt DESC
    """).fetchall()
    if rs:
        print(f'\n{"Region":30s} {"Count":>7s}')
        print('-' * 40)
        for r in rs:
            print(f'{r[0]:30s} {r[1]:>7,}')

    rs = db.execute("""
        SELECT hindu_classification_source, COUNT(*) as cnt
        FROM churches WHERE hindu_classification_source != ''
        GROUP BY hindu_classification_source
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

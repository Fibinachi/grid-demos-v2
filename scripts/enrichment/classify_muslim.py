#!/usr/bin/env python3
"""
Muslim Doctrinal Classification
===============================
Classifies mosques and Islamic centers by doctrinal tradition (Sunni, Shia,
Sufi, Salafi, etc.) using a multi-signal pipeline:

  Step 1 — Name heuristic     (60-70% coverage, very strong)
  Step 2 — Ethnic/geo          (state-level clustering + ethnic inference)
  Step 3 — Website content     (scrapes homepages for doctrinal keywords)
  Step 4 — Confidence scoring  (unified score 0-1)

Usage:
    python scripts/enrichment/classify_muslim.py
    python scripts/enrichment/classify_muslim.py --dry-run
    python scripts/enrichment/classify_muslim.py --reprocess
    python scripts/enrichment/classify_muslim.py --website 100  # Scrape N sites
"""
import argparse, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# ── Confidence thresholds ──
EXPLICIT = 0.95   # explicit doctrinal statement
STRONG_STAFF = 0.85
STRONG_PROG = 0.75
STRONG_NAME = 0.65
ETHNIC = 0.50
GEO = 0.30

# ═══════════════════════════════════════════════════════════════════
# STEP 1 — Name Heuristic Classifier
# ═══════════════════════════════════════════════════════════════════
# Format: (regex_pattern, affiliation, confidence, source_note)

NAME_RULES = [
    # ── Shia (highest priority) ──
    (r'\bimam\s*(jaafar|ali|hussein|mahdi|zaman|sadiq|khomeini|khamenei|sadr)\b', 'Shia (Twelver)', STRONG_NAME, 'imam_pattern'),
    (r'\bja?afari\b', 'Shia (Twelver)', EXPLICIT, 'jafari_keyword'),
    (r'\b(ahlul[-\s]?bayt|ahl[-\s]?al[-\s]?bayt)\b', 'Shia (Twelver)', EXPLICIT, 'ahlulbayt'),
    (r'\bimam[-\s]?(zaman|mahdi)\s*(center|masjid|mosque|islamic)\b', 'Shia (Twelver)', STRONG_NAME, 'imam_mahdi'),
    (r'\bhusayniyya\b', 'Shia (Twelver)', STRONG_NAME, 'husayniyya'),
    (r'\bmajlis\b', 'Shia (Twelver)', STRONG_NAME, 'majlis_term'),
    (r'\bmuharram\b', 'Shia (Twelver)', STRONG_NAME, 'muharram'),
    (r'\bimambargha?\b', 'Shia (Twelver)', STRONG_NAME, 'imambargah'),
    (r'\bazakhana\b', 'Shia (Twelver)', STRONG_NAME, 'azakhana'),
    (r'\bqom\b', 'Shia (Twelver)', STRONG_NAME, 'qom_reference'),
    (r'\b(imam|imam)\s*al[-\s]?(sadiq|ridha|kadhim|askari|baqir|hadi)\b', 'Shia (Twelver)', EXPLICIT, 'imam_name'),
    # Note: "Imam Jaafar AlSadeq Islamic Center" in Detroit → Shia

    # ── Ismaili ──
    (r'\bismaili\b', 'Shia (Ismaili)', EXPLICIT, 'ismaili_name'),
    (r'\bjamatkhana\b', 'Shia (Ismaili)', EXPLICIT, 'jamatkhana'),
    (r'\baga[-\s]?khan\b', 'Shia (Ismaili)', EXPLICIT, 'aga_khan'),
    (r'\bismaili\s*tariqah\b', 'Shia (Ismaili)', EXPLICIT, 'ismaili_tariqah'),

    # ── Bohra (Dawoodi Bohra) ──
    (r'\bbohra\b', 'Shia (Bohra)', EXPLICIT, 'bohra_name'),
    (r'\bdawoodi\s*bohra\b', 'Shia (Bohra)', EXPLICIT, 'dawoodi_bohra'),
    (r'\bal[-\s]?jamea\s*al[-\s]?saifiyah\b', 'Shia (Bohra)', EXPLICIT, 'jamea_saifiyah'),
    (r'\bsyedna\b', 'Shia (Bohra)', EXPLICIT, 'syedna'),
    (r'\bmumin[ea]en?\b', 'Shia (Bohra)', STRONG_NAME, 'mumineen'),

    # ── Sufi (Barelvi / traditional) ──
    (r'\b(sufi|tasawwuf|tariqa[th]?)\b', 'Sunni (Sufi)', STRONG_NAME, 'sufi_name'),
    (r'\b(barelvi|barelwi|ahle[-\s]?sunnat)\b', 'Sunni (Sufi)', EXPLICIT, 'barelvi'),
    (r'\bnaqshbandi\b', 'Sunni (Sufi)', EXPLICIT, 'naqshbandi'),
    (r'\bqadiri?\b', 'Sunni (Sufi)', EXPLICIT, 'qadiri'),
    (r'\bchishti\b', 'Sunni (Sufi)', EXPLICIT, 'chishti'),
    (r'\bsuhrawardi\b', 'Sunni (Sufi)', EXPLICIT, 'suhrawardi'),
    (r'\bdawate\s*islami\b', 'Sunni (Sufi)', EXPLICIT, 'dawate_islami'),
    (r'\bmawlid\b', 'Sunni (Sufi)', STRONG_NAME, 'mawlid'),
    (r'\bzawiya\b', 'Sunni (Sufi)', STRONG_NAME, 'zawiya'),

    # ── Salafi ──
    (r'\bsalafi\b', 'Sunni (Salafi)', EXPLICIT, 'salafi_name'),
    (r'\bahl[-\s]?al[-\s]?hadith\b', 'Sunni (Salafi)', EXPLICIT, 'ahl_al_hadith'),
    (r'\bminhaj[-\s]?al[-\s]?sunnah\b', 'Sunni (Salafi)', EXPLICIT, 'minhaj_sunnah'),
    (r'\bmasjid[-\s]?al[-\s]?furqan\b', 'Sunni (Salafi)', STRONG_NAME, 'furqan'),
    (r'\bdar[-\s]?ul[-\s]?hadith\b', 'Sunni (Salafi)', STRONG_NAME, 'dar_ul_hadith'),
    (r'\bqur[ea]nic[-\s]?center\b', 'Sunni (Salafi)', STRONG_NAME, 'quranic_center'),
    (r'\bahl[-\s]?al[-\s]?tawheed\b', 'Sunni (Salafi)', EXPLICIT, 'tawheed'),

    # ── Deobandi ──
    (r'\bdeobandi\b', 'Sunni (Deobandi)', EXPLICIT, 'deobandi_name'),
    (r'\bdarul[-\s]?uloom\b', 'Sunni (Deobandi)', STRONG_NAME, 'darul_uloom'),
    (r'\btablighi\b', 'Sunni (Deobandi)', STRONG_NAME, 'tablighi'),
    (r'\bdars[-\s]?e[-\s]?nizami\b', 'Sunni (Deobandi)', EXPLICIT, 'dars_nizami'),

    # ── Diyanet (Turkish) ──
    (r'\bdiyanet\b', 'Sunni (Hanafi)', STRONG_NAME, 'diyanet'),
    (r'\bturkish\s*(islamic|mosque|diyanet|center)\b', 'Sunni (Hanafi)', STRONG_NAME, 'turkish'),
    (r'\bturkiye?\s*islamic\b', 'Sunni (Hanafi)', STRONG_NAME, 'turkiye'),

    # ── Nation of Islam ──
    (r'\bnation\s*of\s*islam\b', 'Nation of Islam', EXPLICIT, 'noi_name'),
    (r'\bNOI\b', 'Nation of Islam', EXPLICIT, 'noi_abbr'),
    (r'\bmasjid\s*muhammad\b', 'Nation of Islam', EXPLICIT, 'masjid_muhammad'),
    (r'\bmuhammad\s*mosque\s*\d+\b', 'Nation of Islam', EXPLICIT, 'muhammad_mosque_num'),
    (r'\belijah\s*muhammad\b', 'Nation of Islam', EXPLICIT, 'elijah_muhammad'),
    (r'\bfinal\s*call\b', 'Nation of Islam', EXPLICIT, 'final_call'),

    # ── Ahmadiyya ──
    (r'\bahmadiyy?a\b', 'Ahmadiyya', EXPLICIT, 'ahmadiyya_name'),
    (r'\bmasroor\b', 'Ahmadiyya', EXPLICIT, 'masroor'),
    (r'\bmirza\s*ghulam\b', 'Ahmadiyya', EXPLICIT, 'mirza_ghulam'),
    (r'\bbaitul?\s*(?=[a-z])', 'Ahmadiyya', STRONG_NAME, 'baitul_prefix'),

    # ── Five Percenters ──
    (r'\bfive\s*percent\b', 'Five Percenters', EXPLICIT, 'five_percent'),
    (r'\bgod[ea]s\s*(science|classroom)\b', 'Five Percenters', EXPLICIT, 'godea_science'),
    (r'\ballah\s*school\b', 'Five Percenters', STRONG_NAME, 'allah_school'),

    # ── Quranist (Quran-only) ──
    (r'\bquran[-\s]?only\b', 'Quranist', EXPLICIT, 'quran_only'),
    (r'\bsubmitters?\b', 'Quranist', EXPLICIT, 'submitter'),
    (r'\brashad\s*khalifa\b', 'Quranist', EXPLICIT, 'rashad_khalifa'),

    # ── Ibadhi ──
    (r'\bibad[hi]+\b', 'Ibadhi', EXPLICIT, 'ibadhi_name'),

    # ── Zaydi ──
    (r'\bzaydi\b', 'Shia (Zaydi)', EXPLICIT, 'zaydi_name'),

    # ── Hanafi (South Asian) ──
    (r'\bhanafi\b', 'Sunni (Hanafi)', EXPLICIT, 'hanafi_name'),
    (r'\bbarelvi\b', 'Sunni (Hanafi)', EXPLICIT, 'barelvi_hanafi'),

    # ── Shafi'i (East African / Kurdish) ──
    (r'\bshafi[ei]\b', 'Sunni (Shafi\'i)', EXPLICIT, 'shafii_name'),
    (r'\bsomali\s*(mosque|masjid|center|community|islamic)\b', 'Sunni (Shafi\'i)', STRONG_NAME, 'somali'),
    (r'\bkurdi(?:sh)?\s*(mosque|masjid|center)\b', 'Sunni (Shafi\'i)', STRONG_NAME, 'kurdish'),

    # ── Maliki (West African) ──
    (r'\bmaliki\b', 'Sunni (Maliki)', EXPLICIT, 'maliki_name'),
    (r'\bzaytuna\b', 'Sunni (Maliki)', STRONG_NAME, 'zaytuna'),
    (r'\bsenegalese?\s*islamic\b', 'Sunni (Maliki)', STRONG_NAME, 'senegalese'),

    # ── Hanbali ──
    (r'\bhanbali\b', 'Sunni (Hanbali)', EXPLICIT, 'hanbali_name'),

    # ── Generic ethnic mosque names ──
    (r'\bbosnian\s*(mosque|masjid|center|islamic|dzemal|džemal)\b', 'Sunni (Hanafi)', ETHNIC, 'bosnian'),
    (r'\balbanian\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'albanian'),
    (r'\bturkish\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'turkish_ethnic'),
    (r'\bindonesian\s*(mosque|masjid|center|islamic)\b', 'Sunni (Shafi\'i)', ETHNIC, 'indonesian'),
    (r'\bmalay\s*(mosque|masjid|center|islamic)\b', 'Sunni (Shafi\'i)', ETHNIC, 'malay'),
    (r'\bafghan\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'afghan'),
    (r'\bpakistani\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'pakistani'),
    (r'\bbangladeshi\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'bangladeshi'),
    (r'\bindian\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'indian'),
    (r'\bchinese\s*(mosque|masjid|center|islamic)\b', 'Sunni (Hanafi)', ETHNIC, 'chinese_muslim'),
]

# ── Generic Sunni names (lower confidence, applied last) ──
GENERIC_SUNNI_PATTERNS = [
    (r'\bislamic\s*(society|center|foundation|association|council|community)\b', 'Sunni (Generic)', STRONG_NAME - 0.05, 'generic_islamic'),
    (r'\bmasjid\s+(al[-\s]?)?(salam|huda|noor|islam|falah|tawheed|rahma|iman|ansar|aqsa|nabawi|haram|quds)\b', 'Sunni (Generic)', STRONG_NAME - 0.1, 'masjid_common'),
    (r'\bmasjid\b', 'Sunni (Generic)', ETHNIC, 'masjid_bare'),
    (r'\bmosque\b', 'Sunni (Generic)', ETHNIC, 'mosque_bare'),
    (r'\bislamic\b', 'Sunni (Generic)', ETHNIC, 'islamic_bare'),
    (r'\bmuslim\b', 'Sunni (Generic)', ETHNIC, 'muslim_bare'),
]


# ═══════════════════════════════════════════════════════════════════
# STEP 2 — State-level Ethnic Inference
# ═══════════════════════════════════════════════════════════════════

# High-confidence Shia clusters (Dearborn, Houston, LA, NoVA)
SHIA_CLUSTER_STATES = {
    'MI': 0.40,  # Dearborn = largest Shia concentration in US
    # Others have Shia populations but not majority of mosques
}

# Diyanet/Turkish clusters
TURKISH_CLUSTER_STATES = {}  # Too dispersed, rely on name matching

# Ethnic correlation: state → likely madhhab (fiqh school)
STATE_ETHNIC_INFERENCE = {
    'MN': 'Sunni (Hanafi)',       # Large Somali → Shafi'i, but also big South Asian
    'OH': 'Sunni (Hanafi)',       # Large South Asian + Somali
    'IL': 'Sunni (Hanafi)',       # South Asian predominant
    'NY': 'Sunni (Hanafi)',       # South Asian + Arab
    'NJ': 'Sunni (Hanafi)',       # South Asian predominant
    'TX': 'Sunni (Hanafi)',       # South Asian + Arab
    'CA': 'Sunni (Hanafi)',       # South Asian + Arab + Iranian
    'MI': 'Sunni (Hanafi)',       # Arab + South Asian (Dearborn = Shia outlier)
    'VA': 'Sunni (Hanafi)',       # South Asian + Arab
}

# DO NOT apply state inference alone — only as tiebreaker.
# Name heuristic is much more reliable.


# ═══════════════════════════════════════════════════════════════════
# WEBSITE CONTENT KEYWORDS
# ═══════════════════════════════════════════════════════════════════
WEBSITE_SIGNALS = [
    # Shia signals
    (r'\bja.fari\b', 'Shia (Twelver)', EXPLICIT, 'website_jafari'),
    (r'\bahlul[-\s]?bayt\b', 'Shia (Twelver)', EXPLICIT, 'website_ahlulbayt'),
    (r'\bimam\s+(ali|hussein|mahdi|zaman|khomeini|khamenei|sadiq)\b', 'Shia (Twelver)', STRONG_NAME, 'website_imam'),
    (r'\bqom\s*(seminary|hawza)\b', 'Shia (Twelver)', EXPLICIT, 'website_qom'),
    (r'\bmuharram\s*(program|event|procession|majlis)\b', 'Shia (Twelver)', STRONG_PROG, 'website_muharram'),
    (r'\bashura\b', 'Shia (Twelver)', STRONG_PROG, 'website_ashura'),
    (r'\bmajlis\b', 'Shia (Twelver)', STRONG_PROG, 'website_majlis'),
    (r'\barbaeen\b', 'Shia (Twelver)', STRONG_PROG, 'website_arbaeen'),

    # Sunni Sufi signals
    (r'\bnaghshbandi\b', 'Sunni (Sufi)', EXPLICIT, 'website_naqshbandi'),
    (r'\bqadiri\b', 'Sunni (Sufi)', EXPLICIT, 'website_qadiri'),
    (r'\bchishti\b', 'Sunni (Sufi)', EXPLICIT, 'website_chishti'),
    (r'\btariqa[th]?\b', 'Sunni (Sufi)', EXPLICIT, 'website_tariqa'),
    (r'\bmawlid\s*(an[-\s]?nabi|celebration|program)\b', 'Sunni (Sufi)', STRONG_PROG, 'website_mawlid'),
    (r'\biqra.a\s*bismi', 'Sunni (Generic)', STRONG_NAME, 'website_iqra'),

    # Salafi signals
    (r'\bsalafi\b', 'Sunni (Salafi)', EXPLICIT, 'website_salafi'),
    (r'\bminhaj[-\s]?al[-\s]?sunnah\b', 'Sunni (Salafi)', EXPLICIT, 'website_minhaj'),
    (r'\bahl[-\s]?al[-\s]?hadith\b', 'Sunni (Salafi)', EXPLICIT, 'website_ahl_hadith'),
    (r'\bdar[-\s]?ul[-\s]?hadith\b', 'Sunni (Salafi)', STRONG_NAME, 'website_dar_hadith'),

    # Deobandi signals
    (r'\bdeobandi\b', 'Sunni (Deobandi)', EXPLICIT, 'website_deobandi'),
    (r'\bdarul[-\s]?uloom\b', 'Sunni (Deobandi)', STRONG_NAME, 'website_darul_uloom'),
    (r'\btablighi\s*jama[ea]t\b', 'Sunni (Deobandi)', EXPLICIT, 'website_tablighi'),

    # Staff training signals
    (r'\bgraduate\s*of\s*qom\b', 'Shia (Twelver)', STRONG_STAFF, 'staff_qom'),
    (r'\bal[-\s]?azhar\b', 'Sunni (Generic)', STRONG_STAFF, 'staff_azhar'),
    (r'\bislamic\s*university\s*of\s*medina\b', 'Sunni (Salafi)', STRONG_STAFF, 'staff_medina'),
    (r'\bdarul\s*uloom\b', 'Sunni (Deobandi)', STRONG_STAFF, 'staff_darul_uloom'),
    (r'\bhawza[te]?\s*ilmiyya\b', 'Shia (Twelver)', STRONG_STAFF, 'staff_hawza'),
    (r'\bzaytuna\s*(college|institute|university)\b', 'Sunni (Maliki)', STRONG_STAFF, 'staff_zaytuna'),

    # Ahmadiyya
    (r'\bmasroor\b', 'Ahmadiyya', EXPLICIT, 'website_masroor'),
    (r'\bghulam\s*ahmad\b', 'Ahmadiyya', EXPLICIT, 'website_ghulam_ahmad'),
    (r'\bkhilafat\b', 'Ahmadiyya', STRONG_NAME, 'website_khilafat'),

    # NOI
    (r'\bhonorable\s*elijah\s*muhammad\b', 'Nation of Islam', EXPLICIT, 'website_elijah'),
    (r'\bfinal\s*call\b', 'Nation of Islam', EXPLICIT, 'website_final_call'),
]

# ── Cities with high Shia concentration ──
SHIA_CITIES = {
    'dearborn': ('Shia (Twelver)', 0.55, 'geo_dearborn'),
    'dearborn heights': ('Shia (Twelver)', 0.50, 'geo_dearborn_hts'),
    'hamtramck': ('Shia (Twelver)', 0.45, 'geo_hamtramck'),  # Yemeni Shia
}

# ── Ismaili cluster cities ──
ISMAILI_CITIES = {
    'dallas': ('Shia (Ismaili)', 0.50, 'geo_dallas_ismaili'),
    'houston': ('Shia (Ismaili)', 0.45, 'geo_houston_ismaili'),
    'chicago': ('Shia (Ismaili)', 0.40, 'geo_chicago_ismaili'),
    'atlanta': ('Shia (Ismaili)', 0.40, 'geo_atlanta_ismaili'),
}


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('muslim_affiliation', 'TEXT'),
        ('muslim_confidence', 'REAL'),
        ('muslim_classification_source', 'TEXT'),
        ('muslim_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def classify_by_name(name, city, state):
    """Step 1 — Name heuristic classifier. Returns (affiliation, confidence, source) or None."""
    name_lower = (name or '').lower()
    city_lower = (city or '').lower()

    # Check specific rules first (higher priority)
    for pattern, affiliation, confidence, source in NAME_RULES:
        if re.search(pattern, name_lower):
            return affiliation, confidence, source

    # Check city-level Shia clusters
    if city_lower in SHIA_CITIES:
        affiliation, confidence, source = SHIA_CITIES[city_lower]
        return affiliation, confidence, source

    # Check Ismaili cluster cities
    if city_lower in ISMAILI_CITIES:
        affiliation, confidence, source = ISMAILI_CITIES[city_lower]
        return affiliation, confidence, source

    # Generic Sunni name (lower confidence)
    for pattern, affiliation, confidence, source in GENERIC_SUNNI_PATTERNS:
        if re.search(pattern, name_lower):
            return affiliation, confidence, source

    return None  # No name signal


def classify_by_website(url):
    """Step 3 — Website content classifier. Returns (affiliation, confidence, source) or None."""
    if not url:
        return None

    # Clean URL
    url = url.strip()
    if not url.startswith('http'):
        url = 'http://' + url

    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read(200000).decode('utf-8', 'replace')
    except Exception:
        return None

    html_lower = html.lower()

    best_match = None  # (affiliation, confidence, source)
    for pattern, affiliation, confidence, source in WEBSITE_SIGNALS:
        if re.search(pattern, html_lower):
            if best_match is None or confidence > best_match[1]:
                best_match = (affiliation, confidence, source)

    return best_match


def main():
    parser = argparse.ArgumentParser(description='Muslim doctrinal classification')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--reprocess', action='store_true', help='Reprocess already classified')
    parser.add_argument('--website', type=int, default=0,
                        help='Number of websites to scrape for content signals')
    parser.add_argument('--limit', type=int, default=0, help='Limit records to process')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    # Get Muslim records
    where = '' if args.reprocess else "AND (muslim_affiliation IS NULL OR muslim_affiliation = '')"
    limit = f'LIMIT {args.limit}' if args.limit else ''
    rows = db.execute(f"""
        SELECT id, name, city, state, NULL as website, NULL as fips, faith_tradition
        FROM churches
        WHERE faith = 'Islam'
        {where}
        ORDER BY id
        {limit}
    """).fetchall()

    print(f'Muslim records to classify: {len(rows):,}')

    if args.dry_run:
        for r in rows[:5]:
            result = classify_by_name(r[1], r[2], r[3])
            if result:
                print(f'  {r[0]:>8d} | {r[1][:45]:45s} -> {result[0]:25s} (c={result[1]:.2f}, {result[2]})')
            else:
                print(f'  {r[0]:>8d} | {r[1][:45]:45s} -> no match')
        db.close()
        return

    # ── Phase 1: Name heuristic ──
    name_matches = 0
    name_updates = []

    for r in rows:
        result = classify_by_name(r[1], r[2], r[3])
        if result:
            affiliation, confidence, source = result
            name_updates.append((affiliation, confidence, source, r[0]))
            name_matches += 1

    print(f'\nPhase 1 — Name heuristic: {name_matches:,} / {len(rows):,} matched')

    # Apply name-based classifications
    for affiliation, confidence, source, cid in name_updates:
        db.execute("""
            UPDATE churches SET
                muslim_affiliation = ?,
                muslim_confidence = ?,
                muslim_classification_source = ?,
                muslim_updated = datetime('now')
            WHERE id = ?
        """, (affiliation, confidence, source, cid))

    db.commit()
    print(f'  Written: {name_matches:,} records')

    # ── Phase 2: State-level fallback for unmatched ──
    unmatched = [r for r in rows if r[0] not in {u[3] for u in name_updates}]
    if unmatched:
        unmatched_ids = {r[0] for r in unmatched}
        print(f'Phase 2 — State fallback: {len(unmatched):,} unmatched')
        for r in unmatched:
            state = r[3] or ''
            if state in STATE_ETHNIC_INFERENCE:
                aff = STATE_ETHNIC_INFERENCE[state]
                # Check if this state has Shia cluster
                if state in SHIA_CLUSTER_STATES:
                    # Already classified as something — skip geo override
                    pass
                db.execute("""
                    UPDATE churches SET
                        muslim_affiliation = ?,
                        muslim_confidence = ?,
                        muslim_classification_source = ?,
                        muslim_updated = datetime('now')
                    WHERE id = ?
                """, (aff, ETHNIC, 'state_ethnic_inference', r[0]))

        db.commit()
        print(f'  Written: {len(unmatched):,} records with state inference')

    # ── Phase 3: Website content scraping ──
    if args.website > 0:
        # Get records with websites that are unclassified or low confidence
        web_candidates = db.execute(f"""
            SELECT c.id, c.name, cc.website, c.muslim_affiliation, c.muslim_confidence
            FROM churches c
            LEFT JOIN church_contacts cc ON c.id = cc.church_id
            WHERE c.faith = 'Islam'
            AND cc.website IS NOT NULL
            AND (c.muslim_affiliation IS NULL OR c.muslim_affiliation = ''
                 OR c.muslim_confidence < 0.60)
            ORDER BY RANDOM()
            LIMIT ?
        """, (args.website,)).fetchall()

        print(f'\nPhase 3 — Website scraping: {len(web_candidates):,} candidates')
        web_matched = 0
        for r in web_candidates:
            result = classify_by_website(r[2])
            if result and (r[3] is None or r[3] == '' or result[1] > (r[4] or 0)):
                affiliation, confidence, source = result
                db.execute("""
                    UPDATE churches SET
                        muslim_affiliation = ?,
                        muslim_confidence = ?,
                        muslim_classification_source = ?,
                        muslim_updated = datetime('now')
                    WHERE id = ?
                """, (affiliation, confidence, source, r[0]))
                web_matched += 1
                if web_matched % 50 == 0:
                    db.commit()
                    print(f'    ... {web_matched:,} website matches so far')

        db.commit()
        print(f'  Website matches: {web_matched:,}')

    # ── Report ──
    rs = db.execute("""
        SELECT muslim_affiliation, COUNT(*) as cnt,
               ROUND(AVG(muslim_confidence), 3) as avg_conf
        FROM churches
        WHERE muslim_affiliation != '' AND muslim_affiliation IS NOT NULL
        GROUP BY muslim_affiliation
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Affiliation":30s} {"Count":>7s} {"Avg Conf":>8s}')
    print('-' * 50)
    total_classified = 0
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,} {r[2]:>8.3f}')
        total_classified += r[1]

    rs = db.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith = 'Islam'
        AND (muslim_affiliation IS NULL OR muslim_affiliation = '')
    """).fetchone()
    print(f'\nTotal classified: {total_classified:,}')
    print(f'Still unclassified: {rs[0]:,}')

    # Source breakdown
    rs = db.execute("""
        SELECT muslim_classification_source, COUNT(*) as cnt
        FROM churches
        WHERE muslim_classification_source != '' AND muslim_classification_source IS NOT NULL
        GROUP BY muslim_classification_source
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Source":30s} {"Count":>7s}')
    print('-' * 40)
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

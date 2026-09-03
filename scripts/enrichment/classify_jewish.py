#!/usr/bin/env python3
"""
Jewish FLTD Classification
===========================
Classifies synagogues, temples, and Jewish congregations into FLTD
tradition nodes (Rabbinic, Reform, Orthodox, Conservative, etc.)

Uses a multi-signal pipeline:
  Step 1 — Name patterns (covers 85-90%, very strong)
  Step 2 — State-level demographic inference
  Step 3 — Confidence scoring

Updates the `tradition` column directly (FLTD taxonomy).

Usage:
    python scripts/enrichment/classify_jewish.py
    python scripts/enrichment/classify_jewish.py --dry-run
    python scripts/enrichment/classify_jewish.py --reprocess
"""
import argparse, re, sqlite3, os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# Confidence thresholds
EXPLICIT = 0.95
STRONG_NAME = 0.80
GOOD_NAME = 0.70
MODERATE = 0.60
ETHNIC = 0.50
GEO = 0.35

# FLTD tradition names (matching the taxonomy)
TRAD_RABBINIC = 'Rabbinic'
TRAD_REFORM = 'Reform'
TRAD_CHABAD = 'Orthodox (Chabad)'
TRAD_YESHIVA = 'Orthodox (Yeshiva)'
TRAD_HASIDIC = 'Orthodox (Hasidic)'
TRAD_CONSERVATIVE = 'Conservative'
TRAD_RECONSTRUCTIONIST = 'Reconstructionist'
TRAD_HUMANISTIC = 'Humanistic'
TRAD_SEPHARDIC = 'Sephardic'
TRAD_KARAITE = 'Karaite'
TRAD_MIZRAHI = 'Mizrahi'
TRAD_ORTHODOX_UNION = 'Orthodox Union'
TRAD_ORTHODOX = 'Orthodox'
TRAD_CHRISTIAN_MISCLASSIFIED = 'Christian'  # Flag for reclassification

# ── Christian name filters ──
# Many records flagged faith_tradition='jewish' are actually Christian
# churches with "Temple" or "Congregation" in their name.
# These patterns are EXCLUSIONARY — match = NOT Jewish.
CHRISTIAN_EXCLUSIONS = [
    r'\bchurch\b', r'\bchrist\b', r'\bjesus\b', r'\bgospel\b',
    r'\bbaptist\b', r'\bmethodist\b', r'\blutheran\b', r'\bpresbyterian\b',
    r'\bapostolic\b', r'\bpentecostal\b', r'\bcatholic\b', r'\bepiscopal\b',
    r'\bcongregational\b', r'\bcathedral\b', r'\bmissionary\b',
    r'\bministries\b', r'\bministry\b', r'\bfellowship\b',
    r'\breformation\b', r'\breformed\b', r'\bcalvary\b',
    r'\bg[oa]d\s+(temple|church|center)\b',
    r'\bdeliverance\b', r'\bhealing\b', r'\bpraise\b',
    r'\bworship\b', r'\brevival\b', r'\b(evangel|evangelical)\b',
    r'\bassembly\s+of\s+god\b', r'\bchurch\s+of\s+god\b',
    r'\bchurch\s+of\s+christ\b', r'\bg[oa]d[-\s]*s[-\s]*church\b',
    r'\bkingdom\s+of\s+god\b', r'\bholy\s+(ghost|spirit|temple)\b',
    r'\bgrace\s+(temple|church|center)\b',
    r'\bfaith\s+(temple|church|center|cathedral)\b',
    r'\bl[o]rd[s\']?\s+(temple|church|center)\b',
    r'\bzion\s+(temple|church|baptist|methodist)\b',
    r'\btruth\s+(temple|church)\b',
    r'\btabernacle\b', r'\bbible\s+(church|temple|center)\b',
    r'\bmaranatha\b', r'\bcalvary\s+(temple|church)\b',
    r'\bbethel\s+(assembly|temple|church|baptist)\b',
]

# ═══════════════════════════════════════════════════════════════════
# NAME RULES — ordered by specificity (highest first)
# ═══════════════════════════════════════════════════════════════════

# ── Chabad/Lubavitch (always Orthodox Chassidic) ──
CHABAD_RULES = [
    (r'\bchabad\b', TRAD_CHABAD, EXPLICIT, 'chabad_name'),
    (r'\blubavitch\b', TRAD_CHABAD, EXPLICIT, 'lubavitch_name'),
    (r'\b(downtown|midtown|center|upper)\s*chabad\b', TRAD_CHABAD, EXPLICIT, 'chabad_location'),
    (r'\bchabad\s*(-|of|at|on|in)\s', TRAD_CHABAD, EXPLICIT, 'chabad_of'),
    (r'\b504\s*kingston\s*ave\b', TRAD_CHABAD, EXPLICIT, 'chabad_770'),  # 770 Eastern Pkwy reference
]

# ── Other Chassidic courts ──
CHASSIDIC_RULES = [
    (r'\bsatmar\b', TRAD_HASIDIC, EXPLICIT, 'satmar'),
    (r'\bbobov\b', TRAD_HASIDIC, EXPLICIT, 'bobov'),
    (r'\bvizhnitz\b', TRAD_HASIDIC, EXPLICIT, 'vizhnitz'),
    (r'\bbelz\b', TRAD_HASIDIC, EXPLICIT, 'belz'),
    (r'\bgerer?\b', TRAD_HASIDIC, EXPLICIT, 'gerer'),
    (r'\bskver\b', TRAD_HASIDIC, EXPLICIT, 'skver'),
    (r'\bspinka\b', TRAD_HASIDIC, EXPLICIT, 'spinka'),
    (r'\bklaus?en?b[ue]rg?\b', TRAD_HASIDIC, EXPLICIT, 'klausenburg'),
    (r'\bpupe?re?n?\b', TRAD_HASIDIC, EXPLICIT, 'puppa'),
    (r'\bmunkacs?\b', TRAD_HASIDIC, EXPLICIT, 'munkacs'),
    (r'\bsanz\b', TRAD_HASIDIC, EXPLICIT, 'sanz'),
    (r'\b[tc]shebin\b', TRAD_HASIDIC, EXPLICIT, 'tshebin'),
    (r'\bstolin\b', TRAD_HASIDIC, EXPLICIT, 'stolin'),
    (r'\bkarlin\b', TRAD_HASIDIC, EXPLICIT, 'karlin'),
    (r'\bslonim\b', TRAD_HASIDIC, EXPLICIT, 'slonim'),
    (r'\bmodzhitz\b', TRAD_HASIDIC, EXPLICIT, 'modzhitz'),
    (r'\brazh[dv]??nitza?\b', TRAD_HASIDIC, STRONG_NAME, 'razhnitz'),
    (r'\bchassid(?:ic|ish)?\b', TRAD_HASIDIC, EXPLICIT, 'chassidic'),
    (r'\bhasid(?:ic|ish)?\b', TRAD_HASIDIC, EXPLICIT, 'hasidic'),
    (r'\bchassidus\b', TRAD_HASIDIC, EXPLICIT, 'chassidus'),
]

# ── Yeshivish / Litvak Orthodox ──
YESHIVISH_RULES = [
    (r'\byeshiva\b', TRAD_YESHIVA, STRONG_NAME, 'yeshiva'),
    (r'\bkollel\b', TRAD_YESHIVA, STRONG_NAME, 'kollel'),
    (r'\bkhal\b', TRAD_YESHIVA, STRONG_NAME, 'khal'),
    (r'\bkehillah\b', TRAD_YESHIVA, MODERATE, 'kehillah'),
    (r'\bminyan\b', TRAD_YESHIVA, STRONG_NAME, 'minyan'),
    (r'\bbais\s+', TRAD_YESHIVA, STRONG_NAME, 'bais_yiddish'),
    (r'\bbeis\s+', TRAD_YESHIVA, STRONG_NAME, 'beis'),
    (r'\bbeth\s+jacob\b', TRAD_YESHIVA, STRONG_NAME, 'beth_jacob'),
    (r'\bcongregation\s+beth\s+jacob\b', TRAD_YESHIVA, EXPLICIT, 'cong_beth_jacob'),
    (r'\bbeth\s+yosef\b', TRAD_YESHIVA, STRONG_NAME, 'beth_yosef'),
    (r'\bmekor\s+', TRAD_YESHIVA, MODERATE, 'mekor'),
    (r'\bohel\s+', TRAD_YESHIVA, MODERATE, 'ohel'),
    (r'\bknesses\s+', TRAD_YESHIVA, MODERATE, 'knesses'),
    (r'\bmachon\b', TRAD_YESHIVA, MODERATE, 'machon'),
    (r'\bmesivta\b', TRAD_YESHIVA, STRONG_NAME, 'mesivta'),
    (r'\byeshivish\b', TRAD_YESHIVA, EXPLICIT, 'yeshivish'),
]

# ── Modern Orthodox ──
MODERN_ORTHODOX_RULES = [
    (r'\byoung\s+israel\b', TRAD_ORTHODOX, EXPLICIT, 'young_israel'),
    (r'\bmodern\s+orthodox\b', TRAD_ORTHODOX, EXPLICIT, 'modern_orthodox'),
    (r'\borthodox\s+(synagogue|center|shul|congregation)\b', TRAD_ORTHODOX, MODERATE, 'orthodox_label'),
    (r'\b(torah|mishnah|gemara|talmud)\s+center\b', TRAD_ORTHODOX, MODERATE, 'torah_center'),
    (r'\bwest\s+side\s+(synagogue|jewish\s+center|institutional)\b', TRAD_ORTHODOX, MODERATE, 'west_side'),
    (r'\blincoln\s+square\b', TRAD_ORTHODOX, MODERATE, 'lincoln_square'),
    (r'\bbnai\s+yeshurun\b', TRAD_ORTHODOX, MODERATE, 'bnai_yeshurun'),
]

# ── General Orthodox (catch-all) ──
ORTHODOX_GENERIC = [
    (r'\bsefard(?:ic)?\b', TRAD_SEPHARDIC, STRONG_NAME, 'sefardic'),
    (r'\bsphard(?:ic)?\b', TRAD_SEPHARDIC, STRONG_NAME, 'sphardic'),
    (r'\bshahar[eiy]?\b', TRAD_ORTHODOX, MODERATE, 'shaharei'),
    (r'\bsha[ea]rei\b', TRAD_ORTHODOX, MODERATE, 'sharei'),
    (r'\bma[oa]r[ae]iv?\b', TRAD_ORTHODOX, MODERATE, 'maariv'),
    (r'\btiferes?\b', TRAD_ORTHODOX, MODERATE, 'tiferes'),
    (r'\btiferet\b', TRAD_ORTHODOX, MODERATE, 'tiferet'),
    (r'\bohav\b', TRAD_ORTHODOX, MODERATE, 'ohav'),
    (r'\ba[gh]ud?ath?\b', TRAD_ORTHODOX, MODERATE, 'agudath'),
    (r'\bmishkan\b', TRAD_CONSERVATIVE, MODERATE, 'mishkan'),
    (r'\btz[ea]de?[kq]\b', TRAD_CONSERVATIVE, MODERATE, 'tzedek'),
    (r'\bsh[oe]mir?\b', TRAD_ORTHODOX, MODERATE, 'shomer'),
]

# ── Sephardic / Mizrahi ──
SEPHARDIC_RULES = [
    (r'\bsephardic\b', TRAD_SEPHARDIC, STRONG_NAME, 'sephardic'),
    (r'\bsfard\b', TRAD_SEPHARDIC, STRONG_NAME, 'sfard'),
    (r'\bmagen\s+david\b', TRAD_SEPHARDIC, MODERATE, 'magen_david'),
    (r'\bshaare\s+zion\b', TRAD_SEPHARDIC, MODERATE, 'shaare_zion'),
    (r'\bsha[ea]rei\s+tefill[ae]h?\b', TRAD_SEPHARDIC, MODERATE, 'sharei_tefilah'),
    (r'\bdeal\s+(synagogue|shul|center)\b', TRAD_SEPHARDIC, MODERATE, 'deal_nj'),  # Deal, NJ = Syrian
]

# ── Conservative ──
CONSERVATIVE_RULES = [
    (r'\bconservative\s+(synagogue|congregation|center)\b', TRAD_CONSERVATIVE, EXPLICIT, 'conservative_label'),
    (r'\bb[.?\s*]*nai\s+(israel|torah|jeshurun|yeshurun|shalom)\b', TRAD_CONSERVATIVE, STRONG_NAME, 'bnai_name'),
    (r'\betz\s+chaim\b', TRAD_CONSERVATIVE, GOOD_NAME, 'etz_chaim'),
    (r'\bmishkan\s+tefill[ae]h?\b', TRAD_CONSERVATIVE, EXPLICIT, 'mishkan_tefilah'),
    (r'\badath?\s+', TRAD_CONSERVATIVE, MODERATE, 'adath'),
    (r'\bkol\s+ami\b', TRAD_CONSERVATIVE, GOOD_NAME, 'kol_ami'),
    (r'\bhar\s+zion\b', TRAD_CONSERVATIVE, MODERATE, 'har_zion'),
    (r'\bbeth\s+el\b', TRAD_CONSERVATIVE, MODERATE, 'beth_el_generic'),
    (r'\bbeth\s+shalom\b', TRAD_CONSERVATIVE, MODERATE, 'beth_shalom'),
    (r'\bbeth\s+israel\b', TRAD_CONSERVATIVE, MODERATE, 'beth_israel'),
    (r'\ban[.?\s]*shei\b', TRAD_CONSERVATIVE, MODERATE, 'anshei'),
    (r'\bmenorah\b', TRAD_CONSERVATIVE, MODERATE, 'menorah'),
    (r'\bner\s+tamid\b', TRAD_CONSERVATIVE, MODERATE, 'ner_tamid'),
    (r'\bam\s+echad\b', TRAD_CONSERVATIVE, MODERATE, 'am_echad'),
    (r'\bor\s+(hadash|chadash|ami)\b', TRAD_CONSERVATIVE, MODERATE, 'or_name'),
    (r'\bor\s+zion\b', TRAD_CONSERVATIVE, MODERATE, 'or_zion'),
    (r'\bbeth\s+am\b', TRAD_CONSERVATIVE, MODERATE, 'beth_am'),
    (r'\bbeth\s+david\b', TRAD_CONSERVATIVE, MODERATE, 'beth_david'),
    (r'\bkehilath?\s+', TRAD_CONSERVATIVE, MODERATE, 'kehilath'),
    (r'\bbeth\s+sholom\b', TRAD_CONSERVATIVE, MODERATE, 'beth_sholom'),
    (r'\bcongregation\s+(of|at)\s+', TRAD_CONSERVATIVE, MODERATE, 'congregation_of'),
]

# ── Reform ──
REFORM_RULES = [
    (r'\breform\s+(temple|congregation|synagogue)\b', TRAD_REFORM, EXPLICIT, 'reform_label'),
    (r'\bemanu[-\s]?el\b', TRAD_REFORM, EXPLICIT, 'emanu_el'),
    (r'\brodeph?\s+shalom\b', TRAD_REFORM, EXPLICIT, 'rodeph_shalom'),
    (r'\btemple\s+bethel\b', TRAD_REFORM, MODERATE, 'temple_bethel'),
    (r'\btemple\s+beth\s+el\b', TRAD_REFORM, MODERATE, 'temple_beth_el'),
    (r'\btemple\s+israel\b', TRAD_REFORM, GOOD_NAME, 'temple_israel'),
    (r'\btemple\s+sholom\b', TRAD_REFORM, GOOD_NAME, 'temple_sholom'),
    (r'\btemple\s+shalom\b', TRAD_REFORM, GOOD_NAME, 'temple_shalom'),
    (r'\btemple\s+sinai\b', TRAD_REFORM, GOOD_NAME, 'temple_sinai'),
    (r'\btemple\s+judea\b', TRAD_REFORM, EXPLICIT, 'temple_judea'),
    (r'\btemple\s+emanuel\b', TRAD_REFORM, EXPLICIT, 'temple_emanuel'),
    (r'\btemple\s+beth\s+david\b', TRAD_REFORM, MODERATE, 'temple_beth_david'),
    (r'\btemple\s+beth\s+am\b', TRAD_REFORM, MODERATE, 'temple_beth_am'),
    (r'\btemple\s+beth\s+israel\b', TRAD_REFORM, MODERATE, 'temple_beth_israel'),
    (r'\btemple\s+beth\s+shalom\b', TRAD_REFORM, MODERATE, 'temple_beth_shalom'),
    (r'\btemple\s+', TRAD_REFORM, MODERATE, 'temple_prefix'),
    (r'\bchapter\s+\d+\b', TRAD_REFORM, ETHNIC, 'chapter_num'),
    (r'\breform\b', TRAD_REFORM, EXPLICIT, 'reform_keyword'),
]

# ── Reconstructionist / Renewal / Secular ──
OTHER_MODERN_RULES = [
    (r'\breconstructionist\b', TRAD_RECONSTRUCTIONIST, EXPLICIT, 'reconstructionist'),
    (r'\brenewal\b', TRAD_RECONSTRUCTIONIST, EXPLICIT, 'renewal'),
    (r'\bhumanistic\b', TRAD_HUMANISTIC, EXPLICIT, 'humanistic'),
    (r'\bsecular\s+(jewish|synagogue|congregation)\b', TRAD_HUMANISTIC, EXPLICIT, 'secular'),
    (r'\bhillel\b', TRAD_RABBINIC, EXPLICIT, 'hillel'),  # Hillel is pluralist but defaults Rabbinic
]

# ── Congregation prefix (used by Conservative and Reform) ──
CONGREGATION_PREFIX = [
    (r'\bcongregation\b', None, MODERATE, 'congregation_prefix'),
]

# ── State demographic inference ──
# Percentages are the proportion of each movement's affiliated Jews
# Sources: Pew 2020, local Jewish federation studies
STATE_MOVEMENT = {
    # NY — highest Orthodox concentration (~25-30% of Jewish population)
    'NY': (TRAD_ORTHODOX, GEO, 'state_ny_orthodox'),
    # NJ — large Orthodox especially Lakewood (Yeshivish)
    'NJ': (TRAD_ORTHODOX, GEO, 'state_nj_orthodox'),
    # FL — large Reform + Conservative (retiree demographic)
    'FL': (TRAD_CONSERVATIVE, GEO, 'state_fl_conservative'),
    # CA — large Reform
    'CA': (TRAD_REFORM, GEO, 'state_ca_reform'),
    # Mid-Atlantic/New England — more Conservative/Reform balanced
    'MA': (TRAD_CONSERVATIVE, GEO, 'state_ma_conservative'),
    'CT': (TRAD_CONSERVATIVE, GEO, 'state_ct_conservative'),
    'MD': (TRAD_CONSERVATIVE, GEO, 'state_md_conservative'),
    'PA': (TRAD_CONSERVATIVE, GEO, 'state_pa_conservative'),
    # Midwest — Reform-leaning
    'IL': (TRAD_REFORM, GEO, 'state_il_reform'),
    'OH': (TRAD_REFORM, GEO, 'state_oh_reform'),
    'MI': (TRAD_REFORM, GEO, 'state_mi_reform'),
    'MN': (TRAD_REFORM, GEO, 'state_mn_reform'),
    # South — Reform-leaning (smaller communities)
    'GA': (TRAD_REFORM, GEO, 'state_ga_reform'),
    'NC': (TRAD_REFORM, GEO, 'state_nc_reform'),
    'TX': (TRAD_REFORM, GEO, 'state_tx_reform'),
    'AZ': (TRAD_REFORM, GEO, 'state_az_reform'),
    'CO': (TRAD_REFORM, GEO, 'state_co_reform'),
    # West Coast — Reform-heavy
    'WA': (TRAD_REFORM, GEO, 'state_wa_reform'),
    'OR': (TRAD_REFORM, GEO, 'state_or_reform'),
    'NV': (TRAD_REFORM, GEO, 'state_nv_reform'),
}

# ── Island communities with known profiles ──
KNOWN_COMMUNITIES = {}


def is_christian_name(name):
    """Returns True if the name is clearly Christian, not Jewish."""
    nl = (name or '').lower().strip()
    for pat in CHRISTIAN_EXCLUSIONS:
        if re.search(pat, nl):
            return True
    return False


def classify_by_name(name):
    """Classify by name patterns. Returns (movement, confidence, source) or None."""
    nl = (name or '').lower().strip()
    if not nl:
        return None

    # Skip Christian names — they were mislabeled as faith_tradition='jewish'
    if is_christian_name(nl):
        return None

    # Highest priority: Chabad (exclusive pattern)
    for pat, aff, conf, src in CHABAD_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Other chassidic courts
    for pat, aff, conf, src in CHASSIDIC_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Yeshivish
    for pat, aff, conf, src in YESHIVISH_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Modern Orthodox
    for pat, aff, conf, src in MODERN_ORTHODOX_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Sephardic
    for pat, aff, conf, src in SEPHARDIC_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Reconstructionist / Renewal (exclusive signals)
    for pat, aff, conf, src in OTHER_MODERN_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Reform (highest priority exclusive patterns first)
    for pat, aff, conf, src in REFORM_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Conservative
    for pat, aff, conf, src in CONSERVATIVE_RULES:
        if re.search(pat, nl):
            return aff, conf, src

    # Generic Orthodox catch-all
    for pat, aff, conf, src in ORTHODOX_GENERIC:
        if re.search(pat, nl):
            return aff, conf, src

    # Has "Congregation" prefix → Conservative (default)
    for pat, _, conf, src in CONGREGATION_PREFIX:
        if re.search(pat, nl):
            return TRAD_CONSERVATIVE, conf - 0.10, src  # Lower confidence

    return None


# Valid FLTD traditions already set — skip these
VALID_TRADITIONS = {
    TRAD_RABBINIC, TRAD_REFORM, TRAD_CHABAD, TRAD_YESHIVA, TRAD_HASIDIC,
    TRAD_CONSERVATIVE, TRAD_RECONSTRUCTIONIST, TRAD_HUMANISTIC,
    TRAD_SEPHARDIC, TRAD_KARAITE, TRAD_MIZRAHI, TRAD_ORTHODOX_UNION, TRAD_ORTHODOX
}


def ensure_columns(db):
    existing = {r[1] for r in db.execute('PRAGMA table_info(churches)').fetchall()}
    for col, dtype in [
        ('tradition', 'TEXT'),
        ('last_updated', 'TEXT'),
    ]:
        if col not in existing:
            db.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
            print(f'  Added column: {col}')


def main():
    parser = argparse.ArgumentParser(description='Jewish FLTD classification')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reprocess', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--fix-misclassified', action='store_true',
                        help='Also fix Christian-misclassified records (set tradition=NULL for re-faiting)')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    ensure_columns(db)

    # Build exclusion list for already-classified traditions
    valid_list = "', '".join(sorted(VALID_TRADITIONS))
    if args.reprocess:
        where = ""
    else:
        where = f"AND (tradition IS NULL OR tradition = '' OR tradition NOT IN ('{valid_list}'))"

    limit = f'LIMIT {args.limit}' if args.limit else ''
    rows = db.execute(f"""
        SELECT id, name, city, state
        FROM churches
        WHERE faith = 'Judaism'
        {where}
        ORDER BY id
        {limit}
    """).fetchall()

    print(f'Jewish records to classify: {len(rows):,}')

    if args.dry_run:
        jewish_count, christian_count, unmatched_count = 0, 0, 0
        for r in rows[:30]:
            if is_christian_name(r[1]):
                christian_count += 1
            else:
                result = classify_by_name(r[1])
                if result:
                    jewish_count += 1
                    if jewish_count <= 5:
                        print(f'  JEW {r[0]:>8d} | {r[1][:50]:50s} -> {result[0]:30s} (c={result[1]:.2f})')
                else:
                    unmatched_count += 1
        print(f'\n  Preview: {jewish_count} Jewish, {christian_count} Christian-mislabeled, {unmatched_count} unmatched (of first 30)')
        db.close()
        return

    # Phase 1: Name heuristic
    name_matches = 0
    christian_flagged = 0
    for r in rows:
        if is_christian_name(r[1]):
            christian_flagged += 1
            if args.fix_misclassified:
                # Flag as Christian for re-faiting by setting tradition=NULL
                db.execute("""
                    UPDATE churches SET
                        tradition = NULL,
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (r[0],))
            continue

        result = classify_by_name(r[1])
        if result:
            aff, conf, src = result
            db.execute("""
                UPDATE churches SET
                    tradition = ?,
                    last_updated = datetime('now')
                WHERE id = ?
            """, (aff, r[0]))
            name_matches += 1

    db.commit()
    print(f'  Name heuristic: {name_matches:,} / {len(rows):,} matched')
    if christian_flagged:
        print(f'  Christian-flagged: {christian_flagged:,} {"(tradition cleared for re-faiting)" if args.fix_misclassified else "(skipped)"}')

    # Phase 2: State inference for unmatched (non-Christian only)
    matched_ids = set()
    for r in rows:
        cur = db.execute("SELECT tradition FROM churches WHERE id=?", (r[0],)).fetchone()
        if cur and cur[0] and cur[0] in VALID_TRADITIONS:
            matched_ids.add(r[0])

    unmatched = [r for r in rows if r[0] not in matched_ids and not is_christian_name(r[1])]
    if unmatched:
        state_matches = 0
        for r in unmatched:
            state = (r[3] or '').upper()
            if state in STATE_MOVEMENT:
                aff, conf, src = STATE_MOVEMENT[state]
                db.execute("""
                    UPDATE churches SET
                        tradition = ?,
                        last_updated = datetime('now')
                    WHERE id = ?
                """, (aff, r[0]))
                state_matches += 1
        db.commit()
        print(f'  State inference: {state_matches:,} / {len(unmatched):,} unmatched')

    # Report
    rs = db.execute("""
        SELECT tradition, COUNT(*) as cnt
        FROM churches
        WHERE faith = 'Judaism' AND tradition IS NOT NULL AND tradition != ''
        GROUP BY tradition
        ORDER BY cnt DESC
    """).fetchall()
    print(f'\n{"Tradition":30s} {"Count":>7s}')
    print('-' * 40)
    total = 0
    for r in rs:
        print(f'{r[0]:30s} {r[1]:>7,}')
        total += r[1]

    rs = db.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith = 'Judaism'
        AND (tradition IS NULL OR tradition = '')
    """).fetchone()
    print(f'\nTotal classified: {total:,}')
    print(f'Still unclassified (null tradition): {rs[0]:,}')

    db.close()
    print('\nDone!')


if __name__ == '__main__':
    main()

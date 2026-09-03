"""
Stage 2 Unified Classifier — Classify traditions within each faith.
Usage: python _stage2_unified.py <faith>
Supports: Christian, Islam, Hindu, Buddhist, Judaism, Sikh, Jain, Taoist, Confucian, Bahai, Other

For each faith:
  1. Fix obviously wrong traditions
  2. Normalize capitalization
  3. Classify unclassified (NULL/generic) entries using name patterns + DeepSeek
  4. AI can select "non_religious" to kick back to Stage 1
"""
import sqlite3, os, json, requests, sys, re, time
from datetime import datetime, timezone
from unidecode import unidecode

DB_PATH = r"E:\grid\churches.db"
BATCH_SIZE = 40

# ── Faith-specific configuration ──
FAITH_CONFIG = {
    'Islam': {
        'taxonomy': {
            'sunni': 86, 'shia': 87, 'ibadi': 88, 'sufi': 89, 'ahmadiyya': 690,
            'nation_of_islam': 691, 'quranist': 692, 'non_denominational': 693,
        },
        'name_patterns': [
            (r'\b(sunni|sunna|ahl.?sunna)\b', 'sunni', 0.95),
            (r'\b(shia|shiah|shi\'?a|shitte|twelver|ismaili|zaidi)\b', 'shia', 0.95),
            (r'\b(sufi|sufism|tariqa|qadiri|naqshbandi|chishti|mevlevi|bektashi)\b', 'sufi', 0.95),
            (r'\b(ibadi|ibadhi|ibadiyya)\b', 'ibadi', 0.95),
            (r'\b(ahmadiyya|ahmadi|qadiani)\b', 'ahmadiyya', 0.98),
            (r'\b(salafi|salafiyya|wahhabi)\b', 'sunni', 0.90),
            (r'\b(hanafi|hanafiyya)\b', 'sunni', 0.90),
            (r'\b(maliki|malikiyya)\b', 'sunni', 0.90),
            (r'\b(shafii|shafi\'i|shafiyya)\b', 'sunni', 0.90),
            (r'\b(hanbali|hanbaliyya)\b', 'sunni', 0.90),
            (r'\b(nation of islam|noi)\b', 'nation_of_islam', 0.98),
            (r'\b(masjid|mosque|jamaat|jami\'?a|islamic centre|islamic center)\b', 'sunni', 0.70),
        ],
        'country_defaults': {
            'SA': 'sunni', 'AE': 'sunni', 'QA': 'sunni', 'KW': 'sunni', 'OM': 'sunni',
            'BH': 'sunni', 'YE': 'sunni', 'IQ': 'sunni', 'SY': 'sunni', 'JO': 'sunni',
            'LB': 'sunni', 'PS': 'sunni', 'EG': 'sunni', 'LY': 'sunni', 'TN': 'sunni',
            'DZ': 'sunni', 'MA': 'sunni', 'MR': 'sunni', 'SD': 'sunni', 'SO': 'sunni',
            'TR': 'sunni', 'PK': 'sunni', 'BD': 'sunni', 'MY': 'sunni', 'ID': 'sunni',
            'AF': 'sunni', 'IR': 'shia', 'AZ': 'shia',
            'OM': 'ibadi',
        },
        'non_faith_traditions': ['Mahayana','Theravada','Christian','Protestant','Catholic','Hindu','Vaishnavism','Shaivism','Sikh','Jain','Jewish','Buddhist'],
    },
    'Hindu': {
        'taxonomy': {
            'vaishnavism': 94, 'shaivism': 95, 'shaktism': 96, 'smarta': 97,
            'neo_hindu': 598, 'folk_hinduism': 599, 'balinese_hinduism': 600,
        },
        'name_patterns': [
            (r'\b(vaishnava|vaishnavism|vishnu|krishna|rama|radha|iskcon|hare krishna|swaminarayan)\b', 'vaishnavism', 0.95),
            (r'\b(shaiva|shaivism|shiva|siva|linga|lingam|nataraja)\b', 'shaivism', 0.95),
            (r'\b(shakti|shaktism|devi|durga|kali|parvati|lakshmi|saraswati)\b', 'shaktism', 0.90),
            (r'\b(mandir|temple|kovil|swami)\b', 'vaishnavism', 0.70),
        ],
        'country_defaults': {
            'IN': 'vaishnavism', 'NP': 'shaivism', 'LK': 'shaivism',
            'ID': 'balinese_hinduism', 'MY': 'shaivism',
            'US': 'vaishnavism', 'GB': 'vaishnavism',
        },
        'non_faith_traditions': ['Mahayana','Theravada','Christian','Protestant','Catholic','Islam','Muslim','Sunni','Shia','Sikh','Jain','Jewish'],
    },
    'Buddhist': {
        'taxonomy': {
            'theravada': 63, 'mahayana': 64, 'vajrayana': 65,
            'zen': 66, 'pure_land': 67, 'nichiren': 68,
            'tibetan': 69, 'chinese_buddhism': 70, 'korean_buddhism': 71,
            'shingon': 72, 'tendai': 73,
        },
        'name_patterns': [
            (r'\b(zen|chan|seon|thien)\b', 'zen', 0.95),
            (r'\b(pure land|jodo|shin buddhism|amitabha|amida)\b', 'pure_land', 0.95),
            (r'\b(nichiren|soka gakkai|sgi)\b', 'nichiren', 0.98),
            (r'\b(theravada|vipassana|insight meditation)\b', 'theravada', 0.95),
            (r'\b(tibetan|vajrayana|kagyu|nyingma|gelug|sakya|rinpoche)\b', 'tibetan', 0.95),
            (r'\b(shingon|koyasan|kobo daishi)\b', 'shingon', 0.98),
            (r'\b(tendai|enryakuji)\b', 'tendai', 0.98),
            (r'\b(wat|thai|lao|cambodian|khmer)\b', 'theravada', 0.85),
            (r'\b(temple|tera|ji|dera)\b', 'mahayana', 0.70),
        ],
        'country_defaults': {
            'TH': 'theravada', 'KH': 'theravada', 'LA': 'theravada', 'MM': 'theravada',
            'LK': 'theravada', 'VN': 'mahayana', 'CN': 'mahayana', 'TW': 'mahayana',
            'JP': 'mahayana', 'KR': 'korean_buddhism', 'MN': 'tibetan', 'BT': 'tibetan',
            'NP': 'tibetan',
        },
        'non_faith_traditions': ['Christian','Protestant','Catholic','Islam','Muslim','Hindu','Vaishnavism','Shaivism','Sikh','Jain','Jewish','Shinto'],
    },
    'Judaism': {
        'taxonomy': {
            'rabbinic': 242, 'orthodox': 243, 'orthodox_chabad': 244,
            'orthodox_hasidic': 245, 'orthodox_yeshiva': 246,
            'conservative': 247, 'reform': 248, 'reconstructionist': 249,
            'humanistic': 250, 'sephardic': 251, 'mizrahi': 252, 'karaite': 253,
        },
        'name_patterns': [
            (r'\b(chabad|lubavitch|chabad house)\b', 'orthodox_chabad', 0.98),
            (r'\b(hasidic|hasidim|satmar|bobov|belz|ger|vizhnitz|skver)\b', 'orthodox_hasidic', 0.95),
            (r'\b(yeshiva|yeshivah|beit midrash|kollel)\b', 'orthodox_yeshiva', 0.90),
            (r'\b(reform|progressive|liberal judaism)\b', 'reform', 0.95),
            (r'\b(conservative|masorti|united synagogue)\b', 'conservative', 0.95),
            (r'\b(reconstructionist|recon)\b', 'reconstructionist', 0.98),
            (r'\b(sephardic|sephardi|sefardi)\b', 'sephardic', 0.95),
            (r'\b(orthodox|orthodoxe|ortodoks)\b', 'orthodox', 0.85),
            (r'\b(synagogue|shul|temple|beit|beth|congregation)\b', 'rabbinic', 0.70),
        ],
        'country_defaults': {
            'IL': 'rabbinic', 'US': 'reform', 'GB': 'orthodox',
            'FR': 'sephardic', 'CA': 'conservative', 'AR': 'conservative',
        },
        'non_faith_traditions': ['Christian','Protestant','Catholic','Islam','Muslim','Hindu','Buddhist','Sikh','Jain'],
    },
    'Sikh': {
        'taxonomy': {
            'khalsa': 554, 'singh_sabha': 555, 'nanaksar': 556,
            'ravidassia': 557, 'ramgarhia': 558, 'nirmala': 559, 'namdhari': 560,
        },
        'name_patterns': [
            (r'\b(gurdwara|singh sabha|khalsa)\b', 'khalsa', 0.90),
            (r'\b(nanaksar|nirmala|namdhari|ravidassia|ramgarhia)\b', None, 0.95),  # match by name
        ],
        'country_defaults': {'IN': 'khalsa', 'GB': 'khalsa', 'CA': 'khalsa', 'US': 'khalsa'},
        'non_faith_traditions': ['Christian','Hindu','Islam','Muslim','Buddhist','Jain','Jewish'],
    },
    'Jain': {
        'taxonomy': {
            'digambar': 46, 'shwetambar': 47, 'sthanakvasi': 48, 'terapanth': 49,
        },
        'name_patterns': [
            (r'\b(digambar|digambara)\b', 'digambar', 0.95),
            (r'\b(shwetambar|svetambara|swetambar)\b', 'shwetambar', 0.95),
            (r'\b(sthanakvasi|sthanak)\b', 'sthanakvasi', 0.95),
            (r'\b(terapanth|terapanthi)\b', 'terapanth', 0.95),
        ],
        'country_defaults': {'IN': 'digambar'},
        'non_faith_traditions': ['Christian','Hindu','Islam','Muslim','Buddhist','Sikh'],
    },
    'Taoist': {
        'taxonomy': {
            'folk_taoism': 59, 'quanzhen': 60, 'zhengyi': 61,
            'chinese_folk': 597,
        },
        'name_patterns': [
            (r'\b(quanzhen|全真)\b', 'quanzhen', 0.95),
            (r'\b(zhengyi|正一|天师)\b', 'zhengyi', 0.95),
            (r'\b(taoist|daoist|temple|宫|观|廟|庙)\b', 'folk_taoism', 0.80),
            (r'\b(chinese folk|folk religion|民间信仰)\b', 'chinese_folk', 0.90),
        ],
        'country_defaults': {'TW': 'folk_taoism', 'CN': 'chinese_folk', 'HK': 'folk_taoism', 'SG': 'folk_taoism', 'MY': 'folk_taoism'},
        'non_faith_traditions': ['Christian','Buddhist','Mahayana','Theravada','Zen','Hindu','Islam','Muslim'],
    },
    'Confucian': {
        'taxonomy': {
            'confucianism': 45, 'korean_confucianism': 598,
        },
        'name_patterns': [
            (r'\b(korean|korea)\b', 'korean_confucianism', 0.90),
            (r'\b(confucian|confucius|儒|孔子)\b', 'confucianism', 0.90),
        ],
        'country_defaults': {'KR': 'korean_confucianism', 'CN': 'confucianism', 'TW': 'confucianism'},
        'non_faith_traditions': ['Christian','Buddhist','Hindu'],
    },
    'Bahai': {
        'taxonomy': {
            'bahai': 695,
        },
        'name_patterns': [
            (r'\b(baha.?i|bahai)\b', 'bahai', 0.98),
        ],
        'country_defaults': {},
        'non_faith_traditions': ['Christian','Islam','Muslim','Hindu','Buddhist','Jewish'],
    },
    'Other': {
        'taxonomy': {
            'pagan': 53, 'animist': 39, 'zoroastrian': 61, 'chinese_folk': 597,
            'new_age': 598, 'spiritualist': 599, 'caodaism': 600, 'tenrikyo': 601,
        },
        'name_patterns': [
            (r'\b(pagan|wicca|druid|asatru|heathen)\b', 'pagan', 0.95),
            (r'\b(zoroastrian|parsi|zarathustra)\b', 'zoroastrian', 0.98),
            (r'\b(animist|animism|shaman|shamanism|spirit worship)\b', 'animist', 0.90),
            (r'\b(new age|new thought|metaphysical|spiritualist|spiritualism)\b', 'spiritualist', 0.85),
            (r'\b(cao dai|caodaism)\b', 'caodaism', 0.98),
            (r'\b(chinese folk|folk religion|民间)\b', 'chinese_folk', 0.90),
        ],
        'country_defaults': {},
        'non_faith_traditions': ['Christian','Protestant','Catholic','Islam','Muslim','Hindu','Buddhist','Jewish'],
    },
}

FAITH_CONFIG['Christian'] = {
    'taxonomy': {
        'catholic': 14, 'protestant': 15, 'orthodox': 16, 'anglican': 17,
        'baptist': 18, 'methodist': 19, 'lutheran': 20, 'presbyterian': 21,
        'pentecostal': 22, 'evangelical': 23, 'reformed': 24, 'congregational': 25,
        'adventist': 26, 'mormon': 168, 'jehovahs_witness': 170,
    },
    'name_patterns': [
        (r'\b(catholic|roman catholic)\b', 'catholic', 0.95),
        (r'\b(baptist|southern baptist|sbc)\b', 'baptist', 0.95),
        (r'\b(methodist|umc|wesleyan)\b', 'methodist', 0.95),
        (r'\b(lutheran|elca|lcms|wels)\b', 'lutheran', 0.95),
        (r'\b(presbyterian|pcusa|pca)\b', 'presbyterian', 0.95),
        (r'\b(pentecostal|assemblies of god|aog|cogic)\b', 'pentecostal', 0.95),
        (r'\b(episcopal|anglican|church of england)\b', 'anglican', 0.95),
        (r'\b(orthodox|greek orthodox|russian orthodox|eastern orthodox)\b', 'orthodox', 0.95),
        (r'\b(adventist|seventh.day)\b', 'adventist', 0.95),
        (r'\b(lds|mormon|latter.day saint)\b', 'mormon', 0.98),
        (r'\b(jehovah|jehovas|jw)\b', 'jehovahs_witness', 0.95),
        (r'\b(evangelical|evangelic)\b', 'evangelical', 0.80),
    ],
    'country_defaults': {
        'US': 'protestant', 'BR': 'catholic', 'MX': 'catholic', 'PH': 'catholic',
        'IT': 'catholic', 'ES': 'catholic', 'FR': 'catholic', 'PL': 'catholic',
        'DE': 'protestant', 'GB': 'anglican', 'NG': 'pentecostal', 'ZA': 'protestant',
        'RU': 'orthodox', 'GR': 'orthodox', 'RO': 'orthodox', 'UA': 'orthodox',
    },
    'non_faith_traditions': ['Mahayana','Theravada','Hindu','Vaishnavism','Shaivism','Islam','Muslim','Sunni','Shia','Sikh','Jain','Jewish','Buddhist','Shinto'],
}

# Shinto is already handled
SKIP_FAITHS = {'Shinto'}

def get_config(faith):
    if faith in FAITH_CONFIG:
        return FAITH_CONFIG[faith]
    # Generic fallback
    return {
        'taxonomy': {},
        'name_patterns': [(rf'\b{faith.lower()}\b', faith.lower(), 0.80)],
        'country_defaults': {},
        'non_faith_traditions': [],
    }


def strip_corporate(name):
    """Strip corporate suffixes for cleaner AI classification."""
    if not name: return ""
    n = str(name).strip()
    for suffix in [
        r'\s+INC\.?$', r'\s+INCORPORATED\.?$', r'\s+LLC\.?$', r'\s+LTD\.?$',
        r'\s+LIMITED\.?$', r'\s+CORP\.?$', r'\s+CORPORATION\.?$',
        r'\s+CO\.?$', r'\s+COMPANY\.?$', r'\s+LP\.?$', r'\s+LLP\.?$',
        r'\s+PLC\.?$', r'\s+SARL\.?$', r'\s+GMBH\.?$', r'\s+PTY\.?\s*LTD\.?$',
        r'\s+CHARITABLE TRUST\.?$', r'\s+FOUNDATION\.?$',
    ]:
        n = re.sub(suffix, '', n, flags=re.IGNORECASE)
    return n.strip()


def normalize_display_name(name, name_en=None):
    """Display name: prefer name_english if available, otherwise normalize raw name."""
    # Prefer English name
    if name_en and str(name_en).strip():
        return str(name_en).strip()[:55]
    if not name: return ""
    n = str(name).strip()
    for smart in '\u2019\u2018\u201a\u201b':
        n = n.replace(smart, "'")
    # Transliterate non-Latin scripts (Chinese, Japanese, Arabic, Cyrillic, etc.)
    if not all(ord(c) < 128 for c in n):
        n = unidecode(n)
    if n == n.upper() and len(n) > 4:
        n = n.title()
    n = re.sub(r'\bSt\.(?=\s+[A-Z][a-z])', 'Saint', n)
    n = re.sub(r'\bMt\.(?=\s+[A-Z][a-z])', 'Mount', n)
    return re.sub(r'\s+', ' ', n).strip()[:55]


def classify_by_name(name, patterns):
    """Try name-based classification. Returns (tradition, confidence) or None."""
    if not name: return None
    for pattern, tradition, confidence in patterns:
        if tradition is None:
            # Extract tradition from match
            m = re.search(pattern, name, re.IGNORECASE)
            if m:
                return m.group(1).lower(), confidence
        elif re.search(pattern, name, re.IGNORECASE):
            return tradition, confidence
    return None


def run_stage2(faith):
    config = get_config(faith)
    source_name = f"stage2_{faith.lower()}_classifier"
    generic_tradition = faith.lower()
    
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    
    # ── Phase 1: Fix wrong traditions ──
    non_faith = config['non_faith_traditions']
    if non_faith:
        ph = ','.join(['?' for _ in non_faith])
        wrong = c.execute(f"""
            SELECT COUNT(1) FROM churches WHERE faith=? AND tradition IN ({ph})
        """, [faith] + non_faith).fetchone()[0]
        if wrong > 0:
            print(f"  Fixing {wrong:,} wrong traditions...")
            rows = c.execute(f"""
                SELECT id, name, tradition, landmark_type, country FROM churches 
                WHERE faith=? AND tradition IN ({ph})
                ORDER BY country, name
            """, [faith] + non_faith).fetchall()
            
            for cid, name, old_trad, ltype, country in rows:
                result = classify_by_name(name, config['name_patterns'])
                if result:
                    new_trad, conf = result
                else:
                    new_trad = config['country_defaults'].get(country, generic_tradition)
                    conf = 0.70
                
                tax_id = config['taxonomy'].get(new_trad, None)
                if tax_id:
                    c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (tax_id, cid))
                c.execute("""UPDATE churches SET tradition=?, shinto_confidence=?, shinto_classification_source=?, shinto_updated=datetime('now')
                              WHERE id=?""", (new_trad, conf, f'{source_name}_phase1', cid))
                c.execute("""INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                              VALUES (?,?,?,?,?)""", (cid, 'tradition', old_trad, new_trad, source_name))
            conn.commit()
            print(f"    Fixed {len(rows):,}")
    
    # ── Phase 2: Normalize capitalization ──
    cap_rows = c.execute("""
        SELECT id, tradition FROM churches WHERE faith=? AND tradition=?
    """, (faith, faith)).fetchall()
    if cap_rows:
        for cid, trad in cap_rows:
            c.execute("UPDATE churches SET tradition=? WHERE id=?", (generic_tradition, cid))
        conn.commit()
        print(f"  Normalized {len(cap_rows):,} '{faith}' → '{generic_tradition}'")
    
    # ── Phase 3: Get unclassified ──
    candidates = c.execute("""
        SELECT id, name, city, state, country, landmark_type, faith, tradition
        FROM churches WHERE faith=? AND (tradition IS NULL OR tradition=? OR tradition='')
        AND NOT (name LIKE 'Q%' AND CAST(substr(name,2) AS INTEGER) > 0)
        ORDER BY country, name
    """, (faith, generic_tradition)).fetchall()
    
    c.execute(f"SELECT DISTINCT church_id FROM classification_history WHERE stage='stage2_{faith.lower()}' AND action='classified'")
    already_done = {r[0] for r in c.fetchall()}
    entries = [e for e in candidates if e[0] not in already_done]
    
    print(f"  Candidates: {len(candidates):,} total, {len(entries):,} remaining ({len(already_done):,} done)")
    
    if not entries:
        conn.close()
        return
    
    # ── Phase 4: Name-pattern pre-filter ──
    name_hits = 0
    for e in entries:
        result = classify_by_name(e[1], config['name_patterns'])
        if result:
            trad, conf = result
            tax_id = config['taxonomy'].get(trad, None)
            if tax_id:
                c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (tax_id, e[0]))
            c.execute("""UPDATE churches SET tradition=? WHERE id=?""", (trad, e[0]))
            c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, new_value, confidence, reasoning, batch_id)
                          VALUES (?,'stage2_""" + faith.lower() + """','classified','tradition',?,?,'Name pattern match','stage2_""" + faith.lower() + """_pattern')""",
                       (e[0], trad, conf))
            name_hits += 1
    
    conn.commit()
    already_done.update({e[0] for e in entries if classify_by_name(e[1], config['name_patterns'])})
    
    # ── Phase 4b: Faith redirect pre-filter (for 'Other' faith group) ──
    # If name clearly belongs to a different faith, redirect immediately without AI
    REDIRECT_PATTERNS = [
        (r'\b(pentecostal|baptist|methodist|catholic|anglican|lutheran|presbyterian|episcopal|orthodox|evangelical|charismatic|protestant|church|chapel|cathedral|parish|dioces|worship|ministr|fellowship|christian|jesus|christ|gospel|assembly of god|assemblies of god|adventist|salvation army|reformed church|united church|carmelite|jesuit|franciscan|dominican|benedictine|augustinian)\w*\b', 'Christian'),
        # Denominational abbreviations
        (r'\b(UMC|SBC|ELCA|LCMS|PCUSA|PCA|ABCUSA|ABC-USA|NBC|PNBC|COGIC|AME|AMEZ|CME|UCC|DOC|RCA|CRC|CRCNA|EFCA|IFCA|GARBC|CBA|CBF|BGCT|SBTC|WMU)\b', 'Christian'),
        (r'\b(mosque|masjid|islamic|muslim|jamaat|jami|sunn[i|a]|shia|sufi)\w*\b', 'Islam'),
        (r'\b(mandir|hindu|swami|kovil|devi|krishna|shiva|ganesh|iskcon)\w*\b', 'Hindu'),
        (r'\b(gurdwara|sikh|khalsa|singh sabha)\w*\b', 'Sikh'),
        (r'\b(synagogue|shul|jewish|beit|chabad|lubavitch|torah)\w*\b', 'Judaism'),
        (r'\b(buddhist|buddha|wat\b|vihara|pagoda|theravada|mahayana|zen)\w*\b', 'Buddhist'),
        (r'\b(jain|derasar|digambar|shwetambar)\w*\b', 'Jain'),
        (r'\b(baha.?i|bahai)\w*\b', 'Bahai'),
    ]
    
    redirected = 0
    remaining_entries = []
    for e in entries:
        if e[0] in already_done:
            continue
        name = str(e[1] or '')
        redirected_faith = None
        for pattern, target in REDIRECT_PATTERNS:
            if re.search(pattern, name, re.IGNORECASE):
                if target != faith:  # Only redirect if different from current faith
                    redirected_faith = target
                break
        if redirected_faith:
            civ = {'Christian':'ABRAHAMIC','Islam':'ABRAHAMIC','Judaism':'ABRAHAMIC','Bahai':'ABRAHAMIC',
                   'Hindu':'DHARMIC','Buddhist':'DHARMIC','Sikh':'DHARMIC','Jain':'DHARMIC'}.get(redirected_faith, 'OTHER')
            c.execute("UPDATE churches SET faith=?, tradition=?, civilizational_family=? WHERE id=?",
                       (redirected_faith, redirected_faith.lower(), civ, e[0]))
            c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                          VALUES (?,'stage2_""" + faith.lower() + """','classified','faith',?,?,0.95,?,?)""",
                       (e[0], faith, redirected_faith, f'Name-based redirect: contains {redirected_faith} keyword', f'stage2_{faith.lower()}_redirect'))
            redirected += 1
            already_done.add(e[0])
        else:
            remaining_entries.append(e)
    
    if redirected > 0:
        conn.commit()
        print(f"  Faith redirects: {redirected:,} (name doesn't match {faith})")
    
    entries = remaining_entries
    entries = [e for e in entries if e[0] not in already_done]
    print(f"  Name-pattern: {name_hits:,} matched, {len(entries):,} rem for AI")
    
    # ── Phase 4c: Dedup by name+country before AI ──
    from collections import defaultdict
    name_groups = defaultdict(list)
    for e in entries:
        key = (str(e[1] or '').strip().lower(), str(e[4] or ''))  # name, country
        name_groups[key].append(e)
    deduped = [group[0] for group in name_groups.values()]  # one per unique name+country
    dupes_skipped = len(entries) - len(deduped)
    if dupes_skipped > 0:
        print(f"  Dedup: {dupes_skipped:,} duplicates skipped ({len(entries):,} → {len(deduped):,} unique)")
    entries = deduped
    # Build reverse lookup: unique key → all dup IDs for result broadcasting
    dup_map = {e[0]: [dup[0] for dup in name_groups[(str(e[1] or '').strip().lower(), str(e[4] or ''))]] for e in entries}
    
    if not entries:
        conn.close()
        return
    
    # ── Phase 5: AI classification ──
    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
    if not DEEPSEEK_KEY:
        print("  No DeepSeek API key — skipping AI")
        conn.close()
        return
    
    # Build faith-specific system prompt
    traditions_list = "\n  - ".join(config['taxonomy'].keys())
    
    SYSTEM_PROMPT = f"""You are classifying {faith} religious sites into specific traditions.

Available traditions:
  - {traditions_list}
  - non_religious (use if the entry is NOT actually {faith} — it will be kicked back for re-evaluation)

Rules:
1. **NAME WINS over type/country metadata**: If the name contains "{faith}" (e.g., "Sikh Temple", "Jain Center", "Bahai Assembly"), the entry IS {faith} — NEVER classify as non_religious.
2. **CROSS-FAITH DETECTION**: If the name clearly belongs to a DIFFERENT faith (e.g., "Bola de Neve Church" in Hindu list, "Kalika Mata Temple" in Jain list), use "non_religious" and explain what faith it actually is. This will redirect it correctly. Do NOT force it into a {faith} tradition.
3. Use the entry's NAME as the primary signal. Country and type provide context only.
3. If the name contains definitive keywords for a specific tradition, use it with high confidence.
4. Only select "non_religious" if the name clearly indicates a DIFFERENT religion (e.g., "Kalika Mata Temple" in Jain list → non_religious). Do NOT kick based on landmark_type alone.
5. For ambiguous entries, use the country default or select the most common tradition.
6. Provide an **english_name**: a natural English translation/transliteration of the entry's name.
7. **GARBLED NAMES**: If the name is ALL CAPS, has no spaces, and is >12 characters of unintelligible text (e.g., "PHRATEEPNOIBANGK"), DON'T guess. Use the landmark_type + country as fallback. If type=shrine + country=TH → likely Buddhist. Type=mosque + country=YE → Islam.
8. **PERSON NAMES → JUNK**: If the name looks like just a person's name ("John Smith", "Maria González", "Carlos Oliveira") with no religious keywords (church, temple, mosque, saint, parish, ministry, etc.), classify as "non_religious" with confidence 0.95 and reasoning "Person name, no religious signals". These are database junk, not religious sites.

Return ONLY a JSON array: [{{"idx": N, "tradition": "...", "confidence": 0.0-1.0, "reasoning": "...", "english_name": "..."}}]
"""

    def build_items(chunk):
        return [{"idx": e[0], "name": strip_corporate(str(e[1] or '')), "city": str(e[2] or ''),
                 "state": str(e[3] or ''), "country": str(e[4] or ''),
                 "type": str(e[5] or ''), "current_tradition": str(e[7] or '')}
                for e in chunk]

    def build_user_prompt(items):
        return "\n".join(f'{i["idx"]}. name="{i["name"]}" | type={i["type"]} | country={i["country"]} | city={i["city"]}'
                        for i in items)

    def call_deepseek(items):
        user = build_user_prompt(items)
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions",
                json={"model": "deepseek-chat",
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                   {"role": "user", "content": user}],
                      "temperature": 0.05, "max_tokens": 4000},
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                timeout=120)
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                cleaned = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
                cleaned = re.sub(r'\n?```\s*$', '', cleaned)
                start = cleaned.find('[')
                if start == -1: return None
                depth = 0
                for i in range(start, len(cleaned)):
                    if cleaned[i] == '[': depth += 1
                    elif cleaned[i] == ']':
                        depth -= 1
                        if depth == 0: return json.loads(cleaned[start:i+1])
            return None
        except Exception:
            return None

    total_processed = 0
    total_nonreligious = 0
    counts = {}
    start_time = time.time()
    stage = f"stage2_{faith.lower()}"

    for batch_num in range(0, len(entries), BATCH_SIZE):
        chunk = entries[batch_num:batch_num + BATCH_SIZE]
        items = build_items(chunk)
        bn = batch_num // BATCH_SIZE + 1
        total_batches = (len(entries) - 1) // BATCH_SIZE + 1
        batch_id = f"{stage}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{bn}"

        results = call_deepseek(items)
        if not results:
            time.sleep(2)
            continue

        for r in results:
            idx = r.get("idx")
            tradition = r.get("tradition", generic_tradition)
            confidence = r.get("confidence", 0.7)
            reasoning = r.get("reasoning", "")
            english_name = r.get("english_name", "")

            # Get all duplicate IDs for this entry
            all_ids = dup_map.get(idx, [idx])
            
            for dup_idx in all_ids:
                c.execute("SELECT id, name, city, country, tradition, name_english FROM churches WHERE id=?", (dup_idx,))
                row = c.fetchone()
                if not row: continue
                
                # Store English translation if provided and not already set
                if english_name and english_name.strip() and not row[5]:
                    c.execute("UPDATE churches SET name_english=? WHERE id=?", (english_name.strip(), dup_idx))
                
                ch_name = normalize_display_name(row[1], row[5] or english_name)[:55]
                ch_loc = f"{row[2]}, {row[3]}" if row[2] else str(row[3] or '')
                old_trad = row[4]

            if tradition == 'non_religious':
                # Try to detect actual faith from reasoning for redirect
                redirect_faith = None
                r_lower = reasoning.lower()
                for keyword, target_faith in [
                    ('christian', 'Christian'), ('church', 'Christian'), ('ministry', 'Christian'),
                    ('catholic', 'Christian'), ('catholique', 'Christian'),
                    ('episcopal', 'Christian'), ('archiepiscopal', 'Christian'),
                    ('diocese', 'Christian'), ('diocesan', 'Christian'),
                    ('parish', 'Christian'), ('paroisse', 'Christian'),
                    ('chapel', 'Christian'), ('cathedral', 'Christian'),
                    ('confucius', 'Confucian'), ('confucian', 'Confucian'),
                    ('hindu', 'Hindu'), ('mandir', 'Hindu'), ('swami', 'Hindu'), ('iskcon', 'Hindu'),
                    ('muslim', 'Islam'), ('islamic', 'Islam'), ('mosque', 'Islam'), ('masjid', 'Islam'),
                    ('buddhist', 'Buddhist'), ('buddha', 'Buddhist'), ('wat ', 'Buddhist'),
                    ('jewish', 'Judaism'), ('synagogue', 'Judaism'), ('shul', 'Judaism'),
                    ('sikh', 'Sikh'), ('gurdwara', 'Sikh'),
                    ('jain', 'Jain'), ('derasar', 'Jain'),
                    ('baha', 'Bahai'),
                ]:
                    if keyword in r_lower:
                        redirect_faith = target_faith
                        break
                
                if redirect_faith:
                    # Redirect to correct faith instead of setting Non-Religious — apply to all dupes
                    for dup_idx in all_ids:
                        c.execute("""UPDATE churches SET faith=?, tradition=?, civilizational_family=? WHERE id=?""",
                                   (redirect_faith, redirect_faith.lower(), 
                                    {'Christian':'ABRAHAMIC','Islam':'ABRAHAMIC','Judaism':'ABRAHAMIC','Bahai':'ABRAHAMIC',
                                     'Hindu':'DHARMIC','Buddhist':'DHARMIC','Sikh':'DHARMIC','Jain':'DHARMIC'}.get(redirect_faith, 'OTHER'),
                                    dup_idx))
                        c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                                      VALUES (?,'""" + stage + """','classified','faith',?,?,?,?,?)""",
                                   (dup_idx, faith, redirect_faith, confidence, f'Redirected from {faith}: {reasoning}', batch_id))
                        total_nonreligious += 1
                    print(f"  ↪ {idx:>8} | {ch_name:<50} | {ch_loc:<25} | → {redirect_faith} ({confidence:.2f})  {reasoning}  [x{len(all_ids)}]")
                else:
                    for dup_idx in all_ids:
                        c.execute("""UPDATE churches SET faith='Non-Religious', tradition='non_religious', 
                                      civilizational_family=NULL, taxonomy_id=51 WHERE id=?""", (dup_idx,))
                        c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                                      VALUES (?,'""" + stage + """','kickback','faith',?,?,?,?,?)""",
                                   (dup_idx, faith, 'Non-Religious', confidence, f'Kicked back: {reasoning}', batch_id))
                        total_nonreligious += 1
                    print(f"  ↩ {idx:>8} | {ch_name:<50} | {ch_loc:<25} | NON-RELIGIOUS ({confidence:.2f})  {reasoning}  [x{len(all_ids)}]")
            else:
                tax_id = config['taxonomy'].get(tradition, None)
                for dup_idx in all_ids:
                    if tax_id:
                        c.execute("UPDATE churches SET taxonomy_id=? WHERE id=?", (tax_id, dup_idx))
                    c.execute("""UPDATE churches SET tradition=? WHERE id=?""", (tradition, dup_idx))
                    c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                                  VALUES (?,'""" + stage + """','classified','tradition',?,?,?,?,?)""",
                               (dup_idx, old_trad, tradition, confidence, reasoning, batch_id))
                    counts[tradition] = counts.get(tradition, 0) + 1
                icon = "⚠" if confidence < 0.70 else "✅"
                print(f"  {icon} {idx:>8} | {ch_name:<50} | {ch_loc:<25} | {tradition} ({confidence:.2f})  {reasoning}  [x{len(all_ids)}]")

            total_processed += len(all_ids)

        conn.commit()
        done = min(batch_num + BATCH_SIZE, len(entries))
        pct = done / len(entries) * 100 if entries else 0
        elapsed = time.time() - start_time
        rate = done / elapsed if elapsed > 0 else 0
        eta = (len(entries) - done) / rate if rate > 0 else 0
        print(f"\r  Batch {bn}/{total_batches} | {done:,}/{len(entries):,} ({pct:.1f}%) | "
              f"kicked: {total_nonreligious:,} | {rate:.0f}/s | ETA {eta/60:.0f}m")
        sys.stdout.flush()
        time.sleep(0.5)

    elapsed = time.time() - start_time
    print(f"\n  Done: {total_processed:,} processed, {total_nonreligious:,} kicked back in {elapsed/60:.1f}m")
    if counts:
        for trad, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"    {trad:25s}: {cnt:,}")

    conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python _stage2_unified.py <faith>")
        print("Faiths: Islam, Hindu, Buddhist, Judaism, Sikh, Jain, Taoist, Confucian, Bahai, Other")
        sys.exit(1)
    
    faith = sys.argv[1]
    if faith in SKIP_FAITHS:
        print(f"Skipping {faith} (already handled or too large)")
        sys.exit(0)
    
    print(f"\n{'='*60}")
    print(f"STAGE 2: {faith}")
    print(f"{'='*60}")
    run_stage2(faith)
